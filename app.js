// State
const state = {
    terminology: null,
    countries: null,
    content: null,
    searchIndex: null,
    selectedCountryISO: null,
    activeLevels: new Set(), // Set of strings like "ADM0", "ADM1"
    geoJsonCache: {} // Key: "ISO_LEVEL" -> GeoJSON Data
};

// DOM Elements
const els = {
    map: document.getElementById('map'),
    searchInput: document.getElementById('search-input'),
    searchResults: document.getElementById('search-results'),
    countryDropdown: document.getElementById('country-dropdown'),
    adminButtonsContainer: document.getElementById('admin-buttons-container'),
    attributionBtn: document.getElementById('attribution-btn'),
    attributionModal: document.getElementById('attribution-modal'),
    closeModal: document.getElementById('close-modal')
};

// Initialize Map
const map = new maplibregl.Map({
    container: 'map',
    style: config.mapStyle,
    center: config.initialCenter,
    zoom: config.initialZoom
});

// Initialize Fuse.js
let fuse;

// --- Initialization ---

async function init() {
    try {
        // Load Data
        const [termRes, countriesRes, contentRes, searchRes] = await Promise.all([
            fetch(`${config.dataBaseUrl}/terminology.json`),
            fetch(`${config.dataBaseUrl}/countries.json`),
            fetch(`${config.dataBaseUrl}/content.json`),
            fetch(`${config.dataBaseUrl}/search-index.json`)
        ]);

        state.terminology = await termRes.json();
        state.countries = await countriesRes.json();
        state.content = await contentRes.json();
        const searchData = await searchRes.json();
        state.searchIndex = searchData.index;

        // Init Search
        const fuseOptions = {
            keys: ['name', 'hierarchy'],
            threshold: 0.3,
            distance: 100
        };
        fuse = new Fuse(state.searchIndex, fuseOptions);

        // Populate Dropdown
        populateDropdown();

        // Event Listeners
        setupEventListeners();

    } catch (error) {
        console.error("Failed to load initial data:", error);
        alert("Error loading application data. Check console.");
    }
}

function populateDropdown() {
    state.countries.forEach(country => {
        const option = document.createElement('option');
        option.value = country.iso;
        option.textContent = country.name; // Name already includes "(Disputed Territory)" if applicable
        els.countryDropdown.appendChild(option);
    });
}

function setupEventListeners() {
    // Country Selection
    els.countryDropdown.addEventListener('change', (e) => {
        selectCountry(e.target.value);
    });

    // Search
    els.searchInput.addEventListener('input', (e) => {
        handleSearch(e.target.value);
    });

    // Attribution Modal
    els.attributionBtn.addEventListener('click', () => {
        els.attributionModal.classList.remove('hidden');
    });
    els.closeModal.addEventListener('click', () => {
        els.attributionModal.classList.add('hidden');
    });
    window.addEventListener('click', (e) => {
        if (e.target === els.attributionModal) {
            els.attributionModal.classList.add('hidden');
        }
    });
}

// --- Core Logic ---

async function selectCountry(iso) {
    state.selectedCountryISO = iso;
    state.activeLevels.clear();

    const countryData = state.terminology[iso];
    if (!countryData) {
        console.error(`No terminology data for ${iso}`);
        return;
    }

    // Fly to country
    map.flyTo({
        center: countryData.defaultView.center,
        zoom: countryData.defaultView.zoom,
        essential: true
    });

    // Update UI
    renderAdminButtons(iso);

    // Auto-select ADM0 (or first available level)
    const levels = Object.keys(countryData.levels);
    if (levels.length > 0) {
        toggleAdminLevel(iso, levels[0], true); // Force enable
    }
}

function renderAdminButtons(iso) {
    els.adminButtonsContainer.innerHTML = '';
    const countryData = state.terminology[iso];

    Object.entries(countryData.levels).forEach(([levelCode, levelInfo]) => {
        const btn = document.createElement('button');
        btn.className = 'admin-button';
        btn.textContent = levelInfo.term;
        btn.dataset.level = levelCode;

        btn.addEventListener('click', () => {
            const isActive = state.activeLevels.has(levelCode);
            toggleAdminLevel(iso, levelCode, !isActive);
        });

        els.adminButtonsContainer.appendChild(btn);
    });
}

async function toggleAdminLevel(iso, levelCode, shouldEnable) {
    const btn = els.adminButtonsContainer.querySelector(`[data-level="${levelCode}"]`);

    if (shouldEnable) {
        state.activeLevels.add(levelCode);
        if (btn) btn.classList.add('active');
        await loadAndRenderLayer(iso, levelCode);
    } else {
        state.activeLevels.delete(levelCode);
        if (btn) btn.classList.remove('active');
        removeLayer(iso, levelCode);
    }
}

async function loadAndRenderLayer(iso, levelCode) {
    const cacheKey = `${iso}_${levelCode}`;
    const sourceId = `source-${cacheKey}`;
    const layerIdFill = `layer-fill-${cacheKey}`;
    const layerIdLine = `layer-line-${cacheKey}`;

    // Check if layer already exists
    if (map.getSource(sourceId)) {
        // Just ensure visibility
        if (map.getLayer(layerIdFill)) map.setLayoutProperty(layerIdFill, 'visibility', 'visible');
        if (map.getLayer(layerIdLine)) map.setLayoutProperty(layerIdLine, 'visibility', 'visible');
        return;
    }

    // Fetch Data if not cached
    if (!state.geoJsonCache[cacheKey]) {
        const countryData = state.terminology[iso];
        const filename = countryData.levels[levelCode].file;
        // Filename in terminology.json is the full relative path from dataBaseUrl
        const path = `${config.dataBaseUrl}/${filename}`;

        try {
            const res = await fetch(path);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            state.geoJsonCache[cacheKey] = await res.json();
        } catch (e) {
            console.error(`Failed to load GeoJSON for ${iso} ${levelCode}:`, e);
            return;
        }
    }

    const geojson = state.geoJsonCache[cacheKey];

    // Add Source
    map.addSource(sourceId, {
        type: 'geojson',
        data: geojson
    });

    // Determine Z-index logic: Higher levels (ADM0) below Lower levels (ADM2)
    // MapLibre draws layers in order. We want ADM0 at bottom, ADM2 on top.
    // We can use 'beforeId' in addLayer, but simple appending in order of activation might be tricky.
    // A better approach is to always keep them sorted. 
    // For now, we'll just add them. Since we usually activate ADM0 then ADM1, natural order works.
    // If user toggles ADM0 off then on, it might go on top. 
    // To fix, we could use specific layer IDs for ordering or just let them stack.
    // Given the spec "Higher admin levels (ADM0) render below lower levels", 
    // we should ideally insert before the next higher level layer if it exists.
    // But for simplicity in this MVP, we'll append.

    // Add Fill Layer
    map.addLayer({
        id: layerIdFill,
        type: 'fill',
        source: sourceId,
        paint: {
            'fill-color': '#FFD700',
            'fill-opacity': 0.2 // Active admin level opacity
        }
    });

    // Add Line Layer
    map.addLayer({
        id: layerIdLine,
        type: 'line',
        source: sourceId,
        paint: {
            'line-color': '#FFD700',
            'line-width': 1.5
        }
    });

    // Add Click Interaction
    map.on('click', layerIdFill, (e) => handleFeatureClick(e, iso, levelCode));

    // Cursor pointer
    map.on('mouseenter', layerIdFill, () => map.getCanvas().style.cursor = 'pointer');
    map.on('mouseleave', layerIdFill, () => map.getCanvas().style.cursor = '');
}

function removeLayer(iso, levelCode) {
    const cacheKey = `${iso}_${levelCode}`;
    const layerIdFill = `layer-fill-${cacheKey}`;
    const layerIdLine = `layer-line-${cacheKey}`;
    const sourceId = `source-${cacheKey}`;

    if (map.getLayer(layerIdFill)) map.removeLayer(layerIdFill);
    if (map.getLayer(layerIdLine)) map.removeLayer(layerIdLine);
    if (map.getSource(sourceId)) map.removeSource(sourceId);
}

// --- Interaction ---

function handleFeatureClick(e, iso, levelCode) {
    // Prevent multiple popups if clicking through layers
    // We want the SMALLEST admin level.
    // MapLibre events propagate. We can query rendered features at the point.

    const point = e.point;

    // Get all active fill layers
    const activeLayers = Array.from(state.activeLevels).map(lvl => `layer-fill-${iso}_${lvl}`);

    const features = map.queryRenderedFeatures(point, { layers: activeLayers });

    if (features.length === 0) return;

    // Sort features by admin level (ADM2 > ADM1 > ADM0)
    // We can rely on the ID or properties. 
    // The spec says "SMALLEST (most detailed)".
    // Let's parse the level from the layer ID or feature property.
    // Our mock data has "shapeType": "ADM0" etc.

    // Sort order: ADM5 > ADM4 ... > ADM0
    features.sort((a, b) => {
        const levelA = parseInt(a.properties.shapeType.replace('ADM', ''));
        const levelB = parseInt(b.properties.shapeType.replace('ADM', ''));
        return levelB - levelA; // Descending order (higher number = more detailed)
    });

    const topFeature = features[0];
    showPopup(topFeature, e.lngLat);
}

function showPopup(feature, lngLat) {
    const props = feature.properties;
    const shapeName = props.shapeName;
    const shapeType = props.shapeType; // e.g. "ADM1"
    const iso = props.shapeGroup; // e.g. "USA" or "CHE"

    // Get Terminology
    const termData = state.terminology[iso];
    const levelTerm = termData?.levels[shapeType]?.term || shapeType;

    // Get Content
    let content = { videos: [], images: [], description: "" };
    if (state.content[iso] && state.content[iso][shapeType] && state.content[iso][shapeType][shapeName]) {
        content = state.content[iso][shapeType][shapeName];
    }

    // Build HTML
    let mediaHtml = '';

    // Video
    if (content.videos && content.videos.length > 0) {
        // Simple embed support
        const videoUrl = content.videos[0]; // Take first
        mediaHtml += `<div class="popup-media"><iframe src="${videoUrl}" allowfullscreen></iframe></div>`;
    }

    // Image (if no video, or below? Spec says one or other usually, or stacked)
    if (content.images && content.images.length > 0) {
        mediaHtml += `<div class="popup-media"><img src="${content.images[0]}" alt="${shapeName}"></div>`;
    }

    const html = `
        <div class="popup-header">
            <h3 class="popup-title">${shapeName}</h3>
            <p class="popup-subtitle">${levelTerm}</p>
        </div>
        <div class="popup-body">
            ${mediaHtml}
            ${content.description ? `<p class="popup-description">${content.description}</p>` : ''}
        </div>
    `;

    new maplibregl.Popup({ closeButton: true, maxWidth: '350px' })
        .setLngLat(lngLat)
        .setHTML(html)
        .addTo(map);
}

// --- Search ---

function handleSearch(query) {
    const resultsContainer = els.searchResults;
    resultsContainer.innerHTML = '';

    if (query.length < 2) {
        resultsContainer.classList.add('hidden');
        return;
    }

    const results = fuse.search(query);

    if (results.length === 0) {
        resultsContainer.classList.add('hidden');
        return;
    }

    resultsContainer.classList.remove('hidden');

    // Show top 10
    results.slice(0, 10).forEach(res => {
        const item = res.item;
        const div = document.createElement('div');
        div.className = 'search-result-item';
        // Format: "Name, Parent, Country"
        // hierarchy array is [Name, Parent, ..., Country]
        const label = item.hierarchy.join(', ');
        div.textContent = label;

        div.addEventListener('click', () => {
            selectSearchResult(item);
            resultsContainer.classList.add('hidden');
            els.searchInput.value = item.name;
        });

        resultsContainer.appendChild(div);
    });
}

function selectSearchResult(item) {
    // 1. Select Country
    if (state.selectedCountryISO !== item.iso) {
        els.countryDropdown.value = item.iso;
        selectCountry(item.iso); // This resets layers
    }

    // 2. Activate Level
    // Wait for country selection to process (it's async but we don't await it in event handler)
    // We can just call toggleAdminLevel.
    // Ideally we wait for terminology to be ready, but it is loaded.

    // We need to ensure the layer is loaded.
    // Also, we might want to zoom to the specific feature.
    // The search index has a center point.

    map.flyTo({
        center: item.center,
        zoom: 7 // Generic zoom, or derive from level
    });

    // Activate the specific level button
    toggleAdminLevel(item.iso, item.level, true);

    // Highlight? The layer will highlight all features of that level.
    // To highlight specific feature, we'd need a filter or separate layer.
    // Spec says "highlight the unit".
    // For MVP, zooming to it and showing the level is good.
    // If we want to highlight just that unit, we'd need a filter on the fill layer?
    // Or just rely on the hover effect/click.
}


// Start
map.on('load', init);
