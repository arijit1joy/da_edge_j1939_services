get_dev_info_payload = {
    "method": "get",
    "query": "SELECT DEVICE_OWNER, DOM, cust_ref,equip_id,vin,pcc_claim_status,service_engine_model "
             "FROM da_edge_olympus.DEVICE_INFORMATION WHERE DEVICE_ID "
             "= %(devId)s;",
    "input": {"Params": [{"devId": "devId"}]}
}
