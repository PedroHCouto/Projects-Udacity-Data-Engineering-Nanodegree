from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.amazon.aws.hooks.base_aws import AwsBaseHook
from airflow.models import BaseOperator
from airflow.utils.decorators import apply_defaults
from helpers.sql_create_tables import CreateTable

class StageToRedshiftOperator(BaseOperator):
    """Operator to get data from AWS S3 and stage it into Redshift. 

    Args:
        redshift_conn_id (str): Postgres connection name created by the user on Airflow; 
        aws_conn_id (str): AWS connection name created by the user on Airflow;
        table (str): table in Redshift where the data should be staged into;
        s3_bucket (str): s3 bucket where the source data resides;
        s3_key (str): s3 key to identify the desired data inside the bucket;
        region (str): where the redshift cluster is located;
        ignore_header (int): how many rows should be considered as headers;
        json_type (str): method for reading the JSON file(s). 
            Ether AUTO or JSON file path which maps files and paths; 
    """

    template_fields = ['s3_key']
    copy_template = """
        COPY {}.{}
        FROM '{}'
        ACCESS_KEY_ID '{}'
        SECRET_ACCESS_KEY '{}'
        FORMAT AS JSON '{}'
    """

    @apply_defaults
    def __init__(self,
            redshift_conn_id = 'redshift',
            aws_conn_id = '',
            table = '',
            target_schema = 'public',
            s3_bucket = '',
            s3_key = '',
            json_type = 'auto',
            *args, **kwargs):

        super(StageToRedshiftOperator, self).__init__(*args, **kwargs)
        self.redshift_conn_id = redshift_conn_id
        self.aws_conn_id = aws_conn_id
        self.target_schema = target_schema
        self.table = table
        self.s3_bucket = s3_bucket
        self.s3_key = s3_key
        self.json_type = json_type



    def execute(self, context):  
        self.log.info('StageToRedshiftOperator starting')
        
        # stablish the connections with AWS, Redshift and get the credentials for execute the COPY statements
        self.log.info(f'StageToRedshiftOperator connecting to {self.aws_conn_id} and {self.redshift_conn_id}')
        aws_hook = AwsBaseHook(aws_conn_id = self.aws_conn_id, resource_type = 's3')
        aws_credentials = aws_hook.get_credentials()
        redshift_hook = PostgresHook(postgres_conn_id = self.redshift_conn_id)


        # check which table should be staged
        if 'event' in self.table:
            self.table = 'staging_events'
        else:
            self.table = 'staging_songs' 

        self.log.info("Clearing data from destination Redshift table")
        redshift_hook.run("DELETE FROM {}.{}".format(self.target_schema, self.table))

        # Render the S3_Key and run the copy statement against redshift
        self.log.info('Copying data from S3 to Redsift')
        rendered_key = self.s3_key.format(**context)
        s3_path = "s3://{}/{}".format(self.s3_bucket, rendered_key)

        formatted_query = StageToRedshiftOperator.copy_template.format(
            self.target_schema,
            self.table,
            s3_path,
            aws_credentials.access_key,
            aws_credentials.secret_key,
            self.json_type
        )
        redshift_hook.run(formatted_query)
