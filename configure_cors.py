import boto3

# Credentials from upload_to_r2.py
ACCOUNT_ID = 'cdfbd70fc603bf2d73648b1532d9a3b8'
ACCESS_KEY_ID = '78334d8995e01f7b2a70742e7cdc6d37'
SECRET_ACCESS_KEY = '654cf011f3b6cb46baf8ff5d668cfcdd744e8a0058ee1bdbcf5f83722786ade8'
BUCKET_NAME = 'gadm2'

def set_cors():
    s3 = boto3.client('s3',
        endpoint_url=f'https://{ACCOUNT_ID}.r2.cloudflarestorage.com',
        aws_access_key_id=ACCESS_KEY_ID,
        aws_secret_access_key=SECRET_ACCESS_KEY
    )

    cors_configuration = {
        'CORSRules': [{
            'AllowedHeaders': ['*'],
            'AllowedMethods': ['GET', 'HEAD'],
            'AllowedOrigins': ['*'],
            'ExposeHeaders': ['ETag'],
            'MaxAgeSeconds': 3000
        }]
    }

    print(f"Setting CORS for bucket {BUCKET_NAME}...")
    try:
        s3.put_bucket_cors(Bucket=BUCKET_NAME, CORSConfiguration=cors_configuration)
        print("CORS configuration set successfully.")
    except Exception as e:
        print(f"Error setting CORS: {e}")

if __name__ == "__main__":
    set_cors()
