import os
import csv
import json
import boto3
import requests
import datetime
import utility as util
from multiprocessing import Process
from sqs_utility import sqs_send_message

LOGGER, FILE_NAME = util.logger_and_file_name(__name__)

s3 = boto3.client('s3')
s3_client = boto3.client('s3')
cp_post_bucket = os.environ["CPPostBucket"]
edgeCommonAPIURL = os.environ["edgeCommonAPIURL"]
NGDIBody = json.loads(os.environ["NGDIBody"])
mapTspFromOwner = os.environ["mapTspFromOwner"]


def delete_message_from_sqs_queue(receipt_handle):
    queue_url = os.environ["QueueUrl"]
    sqs_client = boto3.client('sqs')  # noqa
    sqs_message_deletion_response = sqs_client.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)
    LOGGER.debug(f"SQS message deletion response: '{sqs_message_deletion_response}'. . .")
    return sqs_message_deletion_response


def process_ss(ss_rows, ss_dict, ngdi_json_template, ss_converted_prot_header, ss_converted_device_parameters):
    try:
        ss_values = ss_rows[1]  # Get the SS Values row
        LOGGER.debug(f"Single Sample Values: {ss_values}")

        json_sample_head = ngdi_json_template
        LOGGER.debug(f"Received Json Body in SS Handler:{json_sample_head}")

        parameters = {}
        ss_sample = {"convertedDeviceParameters": {}, "convertedEquipmentParameters": []}
        LOGGER.debug(f"Single Sample Converted Protocol Header: {ss_converted_prot_header}")

        converted_prot_header = ss_converted_prot_header.split("~")
        LOGGER.debug(f"Converted Protocol Header Array: {converted_prot_header}")

        try:
            protocol = converted_prot_header[1]
            network_id = converted_prot_header[2]
            address = converted_prot_header[3]
        except IndexError as e:
            LOGGER.error(f"An exception occurred while trying to retrieve the AS protocols network_id and Address:{e}")
            return

        LOGGER.debug(f"Handling the device metadata headers in SS: {ss_converted_device_parameters}")

        for key in ss_converted_device_parameters:
            if key:
                if "messageid" in key.lower():
                    ss_sample["convertedDeviceParameters"][key] = ss_values[ss_dict[key]]
                else:
                    json_sample_head[key] = ss_values[ss_dict[key]]
            del ss_dict[key]

        conv_eq_obj = {"protocol": protocol, "networkId": network_id, "deviceId": address}

        LOGGER.debug(f"Json Sample Head after metadata retrieval: {json_sample_head}")

        for param in ss_dict:
            if "datetimestamp" in param.lower():
                ss_sample["dateTimestamp"] = ss_values[ss_dict[param]]
            elif param:
                parameters[param] = ss_values[ss_dict[param]]

        LOGGER.debug(f"SS Parameters: {parameters}")

        conv_eq_obj["parameters"] = parameters
        LOGGER.debug(f"Converted Equipment Object with Parameters: {conv_eq_obj}")

        ss_sample["convertedEquipmentParameters"].append(conv_eq_obj)
        LOGGER.info(f"Single Sample: {ss_sample}")

        json_sample_head["samples"].append(ss_sample)
        return json_sample_head
    except Exception as e:
        LOGGER.error(f"An exception occurred while handling the Single Sample:{e}")


def process_as(as_rows, as_dict, ngdi_json_template, as_converted_prot_header, as_converted_device_parameters):
    old_as_dict = as_dict
    json_sample_head = ngdi_json_template
    json_sample_head["numberOfSamples"] = len(as_rows)
    LOGGER.debug(f"Original Template from SS to AS {json_sample_head}")

    converted_prot_header = as_converted_prot_header.split("~")
    LOGGER.debug(f"AS Converted Protocol Header array: {converted_prot_header}")
    LOGGER.debug(f"All Sample Rows: {as_rows}")

    try:
        protocol = converted_prot_header[1]
        network_id = converted_prot_header[2]
        address = converted_prot_header[3]
    except IndexError as e:
        LOGGER.error(f"An exception occurred while trying to retrieve the AS protocols network_id and Address: {e}")
        return

    for values in as_rows:
        new_as_dict = {x: old_as_dict[x] for x in old_as_dict}
        parameters = {}
        sample = {"convertedDeviceParameters": {}, "rawEquipmentParameters": [], "convertedEquipmentParameters": [],
                  "convertedEquipmentFaultCodes": []}

        LOGGER.debug(f"OLD AS DICT: {old_as_dict}")
        LOGGER.debug(f"AS DICT: {new_as_dict}")

        for key in as_converted_device_parameters:
            if key:
                sample["convertedDeviceParameters"][key] = values[new_as_dict[key]]

            del new_as_dict[key]

        LOGGER.debug(f"Current Sample with Converted Device Parameters: {sample}")

        conv_eq_obj = {"protocol": protocol, "networkId": network_id, "deviceId": address}

        LOGGER.debug(f"Current ConvertedEquipmentParameters:{conv_eq_obj}")

        for param in new_as_dict:
            if param:
                if "datetimestamp" in param.lower():
                    sample["dateTimestamp"] = values[new_as_dict[param]]
                elif param != "activeFaultCodes" and param != "inactiveFaultCodes" and param != "pendingFaultCodes":
                    parameters[param] = values[new_as_dict[param]]

        conv_eq_obj["parameters"] = parameters
        sample["convertedEquipmentParameters"].append(conv_eq_obj)
        LOGGER.debug(f"Current Sample with Converted Equipment Parameters:{sample}")

        conv_eq_fc_obj = {"protocol": protocol, "networkId": network_id, "deviceId": address, "activeFaultCodes": [],
                          "inactiveFaultCodes": [], "pendingFaultCodes": []}

        if "activeFaultCodes" in new_as_dict:

            ac_fc = values[new_as_dict["activeFaultCodes"]]
            LOGGER.debug(f"Active Faults:{ac_fc}")

            if ac_fc:
                ac_fc_array = ac_fc.split("|")
                for fc in ac_fc_array:
                    if fc:
                        fc_obj = {}
                        fc_arr = fc.split("~")
                        for fc_val in fc_arr:
                            LOGGER.debug(f"Fault Code Value:{fc_val}")
                            fc_obj[fc_val.split(":")[0]] = fc_val.split(":")[1]

                        conv_eq_fc_obj["activeFaultCodes"].append(fc_obj)

        if "inactiveFaultCodes" in new_as_dict:
            inac_fc = values[new_as_dict["inactiveFaultCodes"]]
            if inac_fc:
                ac_fc_array = inac_fc.split("|")
                for fc in ac_fc_array:
                    if fc:
                        fc_obj = {}
                        fc_arr = fc.split("~")
                        for fc_val in fc_arr:
                            fc_obj[fc_val.split(":")[0]] = fc_val.split(":")[1]

                        conv_eq_fc_obj["inactiveFaultCodes"].append(fc_obj)

        if "pendingFaultCodes" in new_as_dict:
            pen_fc = values[new_as_dict["pendingFaultCodes"]]
            if pen_fc:
                ac_fc_array = pen_fc.split("|")
                for fc in ac_fc_array:
                    if fc:
                        fc_obj = {}
                        fc_arr = fc.split("~")
                        for fc_val in fc_arr:
                            fc_obj[fc_val.split(":")[0]] = fc_val.split(":")[1]

                        conv_eq_fc_obj["pendingFaultCodes"].append(fc_obj)

        sample["convertedEquipmentFaultCodes"].append(conv_eq_fc_obj)

        json_sample_head["samples"].append(sample)
        LOGGER.debug(f"Updated JSON Sample Head:{json_sample_head}")

    return json_sample_head


def get_device_id(ngdi_json_template):
    if "telematicsDeviceId" in ngdi_json_template:
        return ngdi_json_template["telematicsDeviceId"]

    return False


def get_tsp_and_cust_ref(device_id):

    get_tsp_cust_ref_payload = {
        "method": "get",
        "query": "select cust_ref, device_owner from da_edge_olympus.device_information WHERE device_id = :devId;",
        "input": {
            "Params": [
                {
                    "name": "devId",
                    "value": {
                        "stringValue": device_id
                    }
                }
            ]
        }
    }

    LOGGER.debug(f"Get TSP and Cust_Ref payload:  {get_tsp_cust_ref_payload}")
    get_tsp_cust_ref_response = requests.post(url=edgeCommonAPIURL, json=get_tsp_cust_ref_payload)
    get_tsp_cust_ref_response_body = get_tsp_cust_ref_response.json()[0]
    get_tsp_cust_ref_response_code = get_tsp_cust_ref_response.status_code

    LOGGER.debug(f"Get TSP and Cust_Ref response code: {get_tsp_cust_ref_response_code}, "
                 f"body: {get_tsp_cust_ref_response_body}")

    if (get_tsp_cust_ref_response_body and get_tsp_cust_ref_response_code == 200) and \
            ("cust_ref" in get_tsp_cust_ref_response_body and get_tsp_cust_ref_response_body["cust_ref"]) and \
            ("device_owner" in get_tsp_cust_ref_response_body and get_tsp_cust_ref_response_body["device_owner"]):
        return get_tsp_cust_ref_response_body

    return {}


def get_cspec_req_id(sc_number):
    if '-' in sc_number:
        config_spec_name = ''.join(sc_number.split('-')[:-1])
        req_id = sc_number.split('-')[-1]
    else:
        config_spec_name = sc_number
        req_id = None
    return config_spec_name, req_id


def retrieve_and_process_file(uploaded_file_object):
    bucket_name = uploaded_file_object["source_bucket_name"]
    file_key = uploaded_file_object["file_key"]
    file_size = uploaded_file_object["file_size"]
    file_key = file_key.replace("%3A", ":")
    LOGGER.info(f"New FileKey: {file_key}")

    obj = s3.get_object(Bucket=bucket_name, Key=file_key)
    csv_file = obj['Body'].read().decode('utf-8').splitlines(True)
    LOGGER.debug(f"Csv File: {csv_file}")

    file_date_time = str(obj['LastModified'])[:19]
    file_metadata = obj["Metadata"]
    LOGGER.debug(f"File Metadata: {file_metadata}")

    fc_uuid = file_metadata['uuid']
    file_name = file_key.split('/')[-1]
    device_id = file_name.split('_')[1]
    esn = file_name.split('_')[2]
    config_spec_name, req_id = get_cspec_req_id(file_name.split('_')[3])

    sqs_message = str(fc_uuid) + "," + str(device_id) + "," + str(file_name) + "," + str(file_size) + "," + str(
        file_date_time) + "," + str('J1939_FC') + "," + str('CSV_JSON_CONVERTED') + "," + str(esn) + "," + str(
        config_spec_name) + "," + str(req_id) + "," + str(None) + "," + " " + "," + " "
    sqs_send_message(os.environ["metaWriteQueueUrl"], sqs_message, edgeCommonAPIURL)

    ngdi_json_template = json.loads(os.environ["NGDIBody"])
    LOGGER.debug(f"NGDI Template: {ngdi_json_template}")

    ss_row = False
    seen_ss = False

    csv_rows = []

    # Get all the rows from the CSV
    for row in csv.reader(csv_file, delimiter=','):
        new_row = list(filter(lambda x: x != '', row))

        if new_row:
            csv_rows.append(row)

    LOGGER.info(f"CSV Rows:  {csv_rows}")

    ss_rows = []
    as_rows = []

    for row in csv_rows:
        if not ss_row and not seen_ss:
            if "messageFormatVersion" in row:
                LOGGER.debug(f"messageFormatVersion row: {row}")
                ngdi_json_template["messageFormatVersion"] = row[1] if row[1] else None
            elif "dataEncryptionSchemeId" in row:
                LOGGER.debug(f"dataEncryptionSchemeId row: {row}")
                ngdi_json_template["dataEncryptionSchemeId"] = row[1] if row[1] else None
            elif "telematicsBoxId" in row:
                LOGGER.debug(f"telematicsBoxId row: {row}")
                ngdi_json_template["telematicsDeviceId"] = row[1] if row[1] else None
            elif "componentSerialNumber" in row:
                LOGGER.debug(f"componentSerialNumber row: {row}")
                ngdi_json_template["componentSerialNumber"] = row[1] if row[1] else None
            elif "dataSamplingConfigId" in row:
                LOGGER.debug(f"dataSamplingConfigId row: {row}")
                ngdi_json_template["dataSamplingConfigId"] = row[1] if row[1] else None
            elif "ssDateTimestamp" in row:
                # Found the Single Sample Row. Append the row as Single Sample row.
                LOGGER.debug(f"ssDateTimestamp Header row: {row}")

                ss_row = True
                seen_ss = True
                ss_rows.append(row)
            elif "asDateTimestamp" in row:
                # If there are no Single Samples, append the row as an All Sample row and stop looking for SS rows
                LOGGER.debug(f"No Single Samples!")
                LOGGER.debug(f"asDateTimestamp Header row: {row}")

                ss_row = False
                seen_ss = True
                as_rows.append(row)
        elif ss_row:
            if "asDateTimestamp" in row:
                LOGGER.error(f"ERROR! Missing the Single Sample Values.")
                return

            LOGGER.debug(f"ssDateTimestamp Values row: {row}")

            ss_rows.append(row)
            ss_row = False
        else:
            as_rows.append(row)

    # Make sure that we received values in the AS (as_rows > 1) and/or SS
    if not seen_ss or (not as_rows) or len(as_rows) < 2:
        LOGGER.error(f"ERROR! Missing the Single Sample Values or the All Samples Values.")
        return

    LOGGER.info(f"NGDI Template after main metadata addition: {ngdi_json_template}")

    ss_dict = {}
    as_dict = {}
    ss_converted_prot_header = ""
    as_converted_prot_header = ""
    count = 0

    ss_headers = ss_rows[0] if ss_rows else []
    LOGGER.debug(f"SS Headers: {ss_headers}")

    as_headers = as_rows[0] if as_rows else []
    LOGGER.debug(f"AS Headers: {as_headers}")

    ss_converted_device_parameters = []
    seen_ss_dev_params = False
    seen_ss_j1939_params = False
    seen_ss_raw_params = False

    as_converted_device_parameters = []
    seen_as_dev_params = False
    seen_as_j1939_params = False
    seen_as_raw_params = False

    # For each of the headers in the SS row, map the index to the header value
    for head in ss_headers:
        if 'device' in head.lower() and 'converted' in head.lower():
            seen_ss_dev_params = True

        if 'j1939' in head.lower() and 'raw' in head.lower():
            seen_ss_raw_params = True

        if 'j1939' in head.lower() and 'converted' in head.lower():
            ss_converted_prot_header = head
            seen_ss_j1939_params = True

        if '~' in head:
            count = count + 1
        elif "datetimestamp" in head.lower():
            ss_dict["dateTimeStamp"] = count
            count = count + 1
        else:
            if seen_ss_dev_params and not seen_ss_raw_params and not seen_ss_j1939_params:
                ss_converted_device_parameters.append(head)

            ss_dict[head] = count
            count = count + 1

    LOGGER.debug(f"SS_DICT: {ss_dict}")
    LOGGER.debug(f"SS Device Headers: {ss_converted_device_parameters}")

    count = 0

    # For each of the headers in the SS row, map the index to the header value
    for head in as_headers:
        if 'j1939' in head.lower() and 'converted' in head.lower():
            as_converted_prot_header = head
            seen_as_j1939_params = True

        if 'j1939' in head.lower() and 'raw' in head.lower():
            seen_as_raw_params = True

        if 'converted' in head.lower() and 'device' in head.lower():
            seen_as_dev_params = True

        if '~' in head:
            count = count + 1
        elif "datetimestamp" in head.lower():
            as_dict["dateTimeStamp"] = count
            count = count + 1
        else:
            if seen_as_dev_params and not seen_as_raw_params and not seen_as_j1939_params:
                as_converted_device_parameters.append(head)

            as_dict[head] = count
            count = count + 1

    LOGGER.debug(f"AS_DICT: {as_dict}")
    LOGGER.debug(f"AS Device Parameters: {as_converted_device_parameters}")

    # Get rid of the AS header row since we have already stored the index of each header
    if as_rows:
        LOGGER.debug(f"Removing AS Header Row --index '0'-- from: {as_rows}")
        del as_rows[0]
        LOGGER.debug(f"New AS Rows: {as_rows}")

    LOGGER.info("Handling Single Samples")
    ngdi_json_template = process_ss(ss_rows, ss_dict, ngdi_json_template, ss_converted_prot_header,
                                    ss_converted_device_parameters) if ss_rows else ngdi_json_template
    LOGGER.debug(f"NGDI JSON Template after SS handling: {ngdi_json_template}")

    LOGGER.info("Handling All Samples")
    ngdi_json_template = process_as(as_rows, as_dict, ngdi_json_template, as_converted_prot_header,
                                    as_converted_device_parameters)
    LOGGER.info(f"NGDI JSON Template after AS handling: {ngdi_json_template}")

    tsp_in_file = "telematicsPartnerName" in ngdi_json_template and ngdi_json_template["telematicsPartnerName"]
    cust_ref_in_file = "customerReference" in ngdi_json_template and ngdi_json_template["customerReference"]
    LOGGER.debug(f"Telematics Partner Name in file: {tsp_in_file}")
    LOGGER.debug(f"Customer Reference in file: {cust_ref_in_file}")

    if not (tsp_in_file and cust_ref_in_file):
        LOGGER.info(f"Retrieve Device ID from file . . .")
        device_id = get_device_id(ngdi_json_template)

        if not device_id:
            LOGGER.error(f"Error! Device ID is not in the file! Aborting!")
            return

        LOGGER.info(f"Retrieving TSP and Customer Reference from EDGE DB . . .")
        got_tsp_and_cust_ref = get_tsp_and_cust_ref(device_id)

        if not got_tsp_and_cust_ref:
            LOGGER.error(f"Error! Could not retrieve TSP and Cust Ref. These are mandatory fields!")
            return

        else:
            tsp_owners = json.loads(mapTspFromOwner)
            tsp_name = tsp_owners[str(got_tsp_and_cust_ref["device_owner"])] if str(
                got_tsp_and_cust_ref["device_owner"]) in tsp_owners else "NA"
            if tsp_name != "NA":
                ngdi_json_template["telematicsPartnerName"] = tsp_name
            else:
                LOGGER.error(f"Error! Could not retrieve TSP. This is mandatory field!")
                return
            ngdi_json_template["customerReference"] = got_tsp_and_cust_ref["cust_ref"]

            LOGGER.debug(f"Final file with TSP and Cust Ref: {ngdi_json_template}")

    LOGGER.info(f"Posting file to S3...")
    filename = file_key
    LOGGER.info(f"Filename: {filename}")

    try:
        LOGGER.info(f"Retrieving date info for File Path from filename . . .")

        file_name_array = filename.split('_')
        LOGGER.debug(f"Split File Name array: {file_name_array}")

        date_component = file_name_array[3]
        LOGGER.debug(f"File Name date component: {date_component}")

        current_datetime = datetime.datetime.strptime(date_component, "%Y%m%d%H%M%S")
        LOGGER.debug(f"File Name date component in datetime format: {current_datetime}")

        store_file_path = "ConvertedFiles/" + esn + '/' + device_id + '/' + ("%02d" % current_datetime.year) + '/' + \
                          ("%02d" % current_datetime.month) + '/' + ("%02d" % current_datetime.day) + '/' + \
                          filename.split('.csv')[0] + '.json'

    except Exception as e:
        LOGGER.error(
            f"An error occurred while trying to get the file path from the file name:{e} Using current date-time . . .")

        current_datetime = datetime.datetime.now()
        LOGGER.debug(f"Current Date Time: {current_datetime}")

        store_file_path = "ConvertedFiles/" + ngdi_json_template['componentSerialNumber'] + '/' + \
                          ngdi_json_template["telematicsDeviceId"] + '/' + ("%02d" % current_datetime.year) + '/' + \
                          ("%02d" % current_datetime.month) + '/' + ("%02d" % current_datetime.day) + '/' + \
                          filename.split('.csv')[0] + '.json'

    LOGGER.info(f"New Filename: {store_file_path}")

    store_file_response = s3_client.put_object(Bucket=cp_post_bucket,
                                               Key=store_file_path,
                                               Body=json.dumps(ngdi_json_template).encode(),
                                               Metadata={'j1939type': 'FC', 'uuid': fc_uuid})

    LOGGER.debug(f"Store File Response: {store_file_response}")

    if store_file_response["ResponseMetadata"]["HTTPStatusCode"] == 200:
        # Delete message from Queue after success
        delete_message_from_sqs_queue(uploaded_file_object["sqs_receipt_handle"])


def lambda_handler(lambda_event, context):  # noqa
    records = lambda_event.get("Records", [])
    processes = []
    LOGGER.debug(f"Received SQS Records: {records}.")
    for record in records:
        s3_event_body = json.loads(record["body"])
        s3_event = s3_event_body['Records'][0]['s3']

        uploaded_file_object = dict(
            source_bucket_name=s3_event['bucket']['name'],
            file_key=s3_event['object']['key'].replace("%", ":").replace("3A", ""),
            file_size=s3_event['object']['size'],
            sqs_receipt_handle=record["receiptHandle"]
        )
        LOGGER.info(f"Uploaded File Object: {uploaded_file_object}.")

        # Retrieve the uploaded file from the s3 bucket and process the uploaded file
        process = Process(target=retrieve_and_process_file, args=(uploaded_file_object,))

        # Make a list of all process to wait and terminate at the end
        processes.append(process)

        # Start process
        process.start()

    # Make sure that all processes have finished
    for process in processes:
        process.join()
