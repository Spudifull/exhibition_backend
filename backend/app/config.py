class Settings:
    branch_env: str

    mongodb_url: str
    database_name: str

    aime_api_url: str
    aime_api_user_id: str
    aime_api_company_code: str

    s3_access_key_id: str
    s3_secret_access_key: str
    s3_region_name: str
    s3_bucket_name: str
    s3_path_prefix: str

    base_image_url: str
    base_json_url: str
    floorplan_service_url: str


settings = Settings()
