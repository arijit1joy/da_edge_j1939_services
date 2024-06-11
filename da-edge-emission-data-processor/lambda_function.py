import sys
import json

sys.path.insert(1, './lib')
import utility as util
from s3_util import get_content
import db_util
from tsb_util import push_to_tsb

LOGGER = util.get_logger(__name__)


def lambda_handler(event, context):
    try:
        LOGGER.info(f"Event posted to Emission Data Processor lambda function is: {event}")
        for record in event['Records']:
            s3_body = json.loads(record['body'])
            LOGGER.info(f"s3_body: {s3_body}")
            for s3_record in s3_body['Records']:
                key = s3_record['s3']['object']['key']
                LOGGER.info(f"fileId: {key}")
                # download file in s3 bucket
                content, uuid = get_content(key)
                content_json = json.loads(content)
                # Get the Request ID
                config_spec_name, req_id = db_util.get_cspec_req_id(content_json['dataSamplingConfigId'])
                data_config_filename = '_'.join(['EDGE', content_json["telematicsDeviceId"], content_json["componentSerialNumber"], config_spec_name])
                request_id, schedular_status = db_util.get_request_id_from_consumption_view('J1939_Emissions', data_config_filename)
                # Updating the scheduler table to data rx in progress
                db_util.update_scheduler_table(request_id , content_json["telematicsDeviceId"] , schedular_status)
                # Send to AAI Cloud
                push_to_tsb(content_json)
                # insert a row in metadata table to FILE_SENT
                db_util.insert_into_metadata_Table(content_json["telematicsDeviceId"], uuid, content_json["componentSerialNumber"], content_json['dataSamplingConfigId'],
                                           key.rsplit('/', 1).pop(), len(content))
    except Exception as e:
        LOGGER.error(f"An error occurred while processing Emission data: {e}")
