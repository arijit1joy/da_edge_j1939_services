import copy
import sys

sys.path.append("../")
import unittest
from unittest.mock import patch, MagicMock


from tests.cda_module_mock_context import CDAModuleMockingContext

with  CDAModuleMockingContext(sys) as cda_module_mock_context, patch.dict("os.environ", {
    "LoggingLevel": "debug",
    "Region": "us-east-1",
    "PTxAPIKey": "123123",
    "PTJ1939Header": '{"Content-Type": "application/json", "Prefer": "param=single-object", "x-api-key": ""}',
    "ptTopicInfo": '{"topicName": "nimbuspt_j1939-j1939-pt-topic", "bu":"PSBU","file_type":"JSON"}',
    "Latitude": "39.202938",
    "Longitude": "-85.88672",
    "mskSecretArn": "mskSecretArn",
    "mskClusterArn": "mskClusterArn",
    "KafkaApiVersionTuple": "(1, 2, 3)"

}):
    cda_module_mock_context.mock_module("boto3")
    cda_module_mock_context.mock_module("post")
    cda_module_mock_context.mock_module("requests")
    cda_module_mock_context.mock_module("utility")
    cda_module_mock_context.mock_module("update_scheduler")
    cda_module_mock_context.mock_module("edge_sqs_utility_layer")
    cda_module_mock_context.mock_module("edge_kafka_utility_layer")
    cda_module_mock_context.mock_module("edge_gps_utility_layer")
    cda_module_mock_context.mock_module("edge_db_simple_layer")
    cda_module_mock_context.mock_module("edge_secretsmanager_utility_layer")

    import pt_poster

class MyTestCase(unittest.TestCase):
    """
    Test module for pt_poster.py
    """

    post_url = "https://json"
    headers = '{"Content-Type": "application/json", "Prefer": "param=single-object", "x-api-key": ""}'

    hb_params = {
        "CPU_Usage_Level": "2.02",
        "LTE_RSRP": "-107",
        "LTE_RSRQ": "-6",
        "messageID": "8c5a1650-048e-4620-9950-bc14fa4b46b7",
        "Latitude": "39.202938",
        "CPU_temperature": "40.3",
        "Satellites_Used": "20",
        "Longitude": "-85.88672",
        "PDOP": "1.159999967",
        "LTE_RSCP": "255",
        "PMIC_temperature": "33.25",
        "LTE_RSSI": "99",
        "Altitude": "165.236"
    }

    fc_params = [
        {
            "protocol": "J1939",
            "networkId": "CAN1",
            "deviceId": "0",
            "activeFaultCodes": [
                {"spn": "100", "fmi": "4", "count": "1"},
                {"spn": "101", "fmi": "4", "count": "1"}
            ],
            "inactiveFaultCodes": [],
            "pendingFaultCodes": []
        }
    ]

    json_body = {
        "messageFormatVersion": "1.1.1",
        "telematicsPartnerName": "Cummins",
        "customerReference": "Cummins",
        "componentSerialNumber": "CMMNS**19299954**************************************************************",
        "equipmentId": "EDGE_19299954",
        "vin": "TESTVIN19299954",
        "telematicsDeviceId": "192999999999954",
        "dataSamplingConfigId": "Event1_5",
        "dataEncryptionSchemeId": "ES1",
        "numberOfSamples": 1,
        "samples": [
            {
                "convertedDeviceParameters": hb_params, 
                "rawEquipmentParameters": [],
                "convertedEquipmentParameters": [
                    {
                        "protocol": "J1939",
                        "networkId": "CAN1",
                        "deviceId": "0",
                        "parameters": {
                            "190": "",
                            "174": "",
                            "175": "",
                            "110": "",
                            "100": "",
                            "101": "",
                            "102": "",
                            "168": "",
                            "157": "",
                            "105": "",
                            "513": "",
                            "899": "",
                            "91": "",
                            "92": "",
                            "109": ""
                        }
                    }
                ],
                "convertedEquipmentFaultCodes": fc_params,
                "dateTimestamp": "2021-02-09T12:30:00.015Z"
             }
        ]
    }
    j1939_data_type = "FC"
    j1939_type = "FC"
    file_uuid = "88123123123"

    device_id = "192999999999954"

    config_spec_and_req_id = "1234"

    file_name = "TestKafka"
    file_size = "10"
    esn = "CMMNS**19299954**************************************************************"
    sqs_message_template = \
        f"{file_uuid},{device_id},{file_name},{str(file_size)}," \
        f"{'{FILE_METADATA_CURRENT_DATE_TIME}'},{j1939_data_type}," \
        f"{'{FILE_METADATA_FILE_STAGE}'},{esn},{config_spec_and_req_id}"

    headers_json = {"x-api-key": "12345"}


    def test_handle_fc_params_successful(self):
        """
        Test for handle_fc_params() running successfully.
        """
        converted_fc_params = [
            {
                "protocol": "J1939",
                "networkId": "CAN1",
                "deviceId": "0",
                "activeFaultCodes": [
                    {"spn": "100", "fmi": "4", "occurenceCount": "1"},
                    {"spn": "101", "fmi": "4", "occurenceCount": "1"}
                ]
            }
        ]

        response = pt_poster.handle_fc_params(self.fc_params)

        self.assertEqual(response, converted_fc_params)


    @patch("pt_poster.handle_gps_coordinates")
    def test_handle_hb_params_successful(self, mock_handle_gps_coords):
        """
        Test for handle_hb_params() running successfully.
        """
        converted_hb_params = {
            "latitude": "lat",
            "longitude": "long",
            "altitude": "165.236"
        }

        mock_handle_gps_coords.return_value = ("lat", "long")

        response = pt_poster.handle_hb_params(copy.deepcopy(self.hb_params))

        mock_handle_gps_coords.assert_called_with("39.202938", "-85.88672", deobfuscate=True)
        self.assertEqual(response, converted_hb_params)


    @patch("pt_poster.write_health_parameter_to_database_v2")
    def test_store_device_health_params_successful(self, mock_write_health_params):
        """
        Test for store_device_health_params running successfully.
        """
        pt_poster.store_device_health_params(
            self.hb_params,
            "2024-01-17T05:54:00.503Z",
            self.device_id,
            self.esn
        )
        
        mock_write_health_params.assert_called_with(
            "8c5a1650-048e-4620-9950-bc14fa4b46b7",
            "40.3",
            "33.25",
            "39.202938",
            "-85.88672",
            "165.236",
            "1.159999967",
            "20",
            "99",
            "255",
            "-6",
            "-107",
            "2.02",
            None,
            None,
            "2024-01-17 05:54:00",
            self.device_id,
            self.esn
        )


    @patch.dict('os.environ', {'publishKafka': 'False'})
    @patch("pt_poster.requests")
    @patch("pt_poster.LOGGER")
    @patch("pt_poster.publish_message")
    @patch("pt_poster.create_irs_message")
    @patch("pt_poster.store_device_health_params")
    @patch("pt_poster.handle_hb_params")
    @patch("pt_poster.get_json_value_from_secrets_manager")
    def test_send_to_pt_given(self, mocK_sec_client: MagicMock,
                              hb_params: MagicMock(), health_params: MagicMock,
                              create_kafka: MagicMock, publish_message: MagicMock,
                              mock_logger: MagicMock, mock_requests: MagicMock):
        mocK_sec_client.return_value = self.headers_json
        hb_params.return_value = self.hb_params

        pt_poster.send_to_pt(self.post_url,
                             self.headers, self.json_body, self.sqs_message_template, self.j1939_data_type,
                             self.j1939_type,
                             self.file_uuid, self.device_id, self.esn)
        create_kafka.assert_not_called()
        publish_message.assert_not_called()

    @patch.dict('os.environ', {'publishKafka': 'True'})
    @patch("pt_poster.LOGGER")
    @patch("pt_poster.requests")
    @patch("pt_poster.publish_message")
    @patch("pt_poster.create_irs_message")
    @patch("pt_poster.store_device_health_params")
    @patch("pt_poster.handle_hb_params")
    @patch("pt_poster.get_json_value_from_secrets_manager")
    def test_send_to_pt_given_publish_kafka_then_publish_message(self, mocK_sec_client: MagicMock,
                                                                 hb_params: MagicMock(), health_params: MagicMock,
                                                                 create_kafka: MagicMock, publish_message: MagicMock,
                                                                 mock_requests: MagicMock, mock_util: MagicMock):
        mocK_sec_client.return_value = self.headers_json
        hb_params.return_value = self.hb_params
        pt_poster.send_to_pt(self.post_url,
                             self.headers, self.json_body, self.sqs_message_template, self.j1939_data_type,
                             self.j1939_type,
                             self.file_uuid, self.device_id, self.esn)
        create_kafka.assert_called_once()
        publish_message.assert_called_once()


if __name__ == '__main__':
    unittest.main()
