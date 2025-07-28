import os
import subprocess
import boto3
import logging
from datetime import datetime
import gzip

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
DB_HOST = os.environ['DB_HOST']
DB_NAME = os.environ['DB_NAME']
DB_USER = os.environ['DB_USER']
DB_PASSWORD = os.environ['DB_PASSWORD']
S3_BUCKET = os.environ['S3_BUCKET']
S3_PREFIX = os.environ['S3_PREFIX']
ENVIRONMENT = os.environ['ENVIRONMENT']

# AWS clients
s3_client = boto3.client('s3')

def handler(event, context):
    """
    Lambda handler for database backup
    """
    try:
        # Generate timestamp
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        
        # Create backup filename
        backup_filename = f"{DB_NAME}_{ENVIRONMENT}_{timestamp}.sql"
        compressed_filename = f"{backup_filename}.gz"
        local_backup_path = f"/tmp/{backup_filename}"
        local_compressed_path = f"/tmp/{compressed_filename}"
        
        logger.info(f"Starting database backup for {DB_NAME}")
        
        # Set PostgreSQL password
        os.environ['PGPASSWORD'] = DB_PASSWORD
        
        # Create pg_dump command
        pg_dump_cmd = [
            'pg_dump',
            '-h', DB_HOST.split(':')[0],  # Extract hostname without port
            '-U', DB_USER,
            '-d', DB_NAME,
            '-f', local_backup_path,
            '--verbose',
            '--no-owner',
            '--no-acl'
        ]
        
        # Run pg_dump
        logger.info("Running pg_dump...")
        result = subprocess.run(pg_dump_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"pg_dump failed: {result.stderr}")
            raise Exception(f"pg_dump failed with return code {result.returncode}")
        
        logger.info("pg_dump completed successfully")
        
        # Compress the backup
        logger.info("Compressing backup...")
        with open(local_backup_path, 'rb') as f_in:
            with gzip.open(local_compressed_path, 'wb') as f_out:
                f_out.writelines(f_in)
        
        # Get file size
        file_size = os.path.getsize(local_compressed_path)
        logger.info(f"Compressed backup size: {file_size / 1024 / 1024:.2f} MB")
        
        # Upload to S3
        s3_key = f"{S3_PREFIX}{compressed_filename}"
        logger.info(f"Uploading to S3: s3://{S3_BUCKET}/{s3_key}")
        
        s3_client.upload_file(
            local_compressed_path,
            S3_BUCKET,
            s3_key,
            ExtraArgs={
                'ServerSideEncryption': 'AES256',
                'Metadata': {
                    'environment': ENVIRONMENT,
                    'database': DB_NAME,
                    'timestamp': timestamp,
                    'size': str(file_size)
                }
            }
        )
        
        logger.info("Upload completed successfully")
        
        # Clean up local files
        os.remove(local_backup_path)
        os.remove(local_compressed_path)
        
        return {
            'statusCode': 200,
            'body': {
                'message': 'Database backup completed successfully',
                'backup_location': f"s3://{S3_BUCKET}/{s3_key}",
                'size_mb': file_size / 1024 / 1024,
                'timestamp': timestamp
            }
        }
        
    except Exception as e:
        logger.error(f"Backup failed: {str(e)}")
        raise