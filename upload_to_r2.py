import boto3
import os
import mimetypes

# R2 Credentials from APIs.md
ACCOUNT_ID = 'cdfbd70fc603bf2d73648b1532d9a3b8'
ACCESS_KEY_ID = '78334d8995e01f7b2a70742e7cdc6d37'
SECRET_ACCESS_KEY = '654cf011f3b6cb46baf8ff5d668cfcdd744e8a0058ee1bdbcf5f83722786ade8'
BUCKET_NAME = 'gadm2'

def upload_directory(path, bucket_name):
    s3 = boto3.client('s3',
        endpoint_url=f'https://{ACCOUNT_ID}.r2.cloudflarestorage.com',
        aws_access_key_id=ACCESS_KEY_ID,
        aws_secret_access_key=SECRET_ACCESS_KEY
    )

    print(f"Uploading {path} to {bucket_name}...")

    for root, dirs, files in os.walk(path):
        for file in files:
            local_path = os.path.join(root, file)
            # Construct key to maintain folder structure
            # e.g. geoboundaries-data/terminology.json
            relative_path = os.path.relpath(local_path, os.path.dirname(path))
            s3_key = relative_path

            # Guess content type
            content_type, _ = mimetypes.guess_type(local_path)
            if content_type is None:
                content_type = 'application/octet-stream'

            print(f"Uploading {local_path} to {s3_key} ({content_type})...")
            
            try:
                s3.upload_file(
                    local_path, 
                    bucket_name, 
                    s3_key,
                    ExtraArgs={'ContentType': content_type}
                )
            except Exception as e:
                print(f"Failed to upload {local_path}: {e}")

    print("Upload complete!")

if __name__ == "__main__":
    # Upload the geoboundaries-data folder
    upload_directory('geoboundaries-data', BUCKET_NAME)
