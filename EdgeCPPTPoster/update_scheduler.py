import boto3
import os
import edge_core as edge
from pypika import Query, Table, Order, functions as fn

db_api_url = os.environ["EdgeCommonDBAPI"]

def get_request_id_from_consumption_view(data_protocol, data_config_filename):
    data_protocol = 'eFPA' if data_protocol == 'EFPA' else data_protocol
    query = get_request_id_from_consumption_view_query(data_protocol, data_config_filename)
    request_id = ''
    print(query)
    try:
        request_id = edge.api_request(db_api_url, "get", query)
        print('Successfully fetch request id from view')
    except Exception as exception:
        print('Failed to fetch request id from consumption view ')
        return edge.server_error(str(exception))
    return request_id

def get_request_id_from_consumption_view_query(data_protocol, data_config_filename):
    data_consumption_vw = Table('da_edge_olympus.edge_data_consumption_vw')
    query = Query.from_(data_consumption_vw).select(data_consumption_vw.request_id).where(
        data_consumption_vw.data_type == data_protocol
    ).where(data_consumption_vw.data_config_filename == data_config_filename)
    return query.get_sql(quote_char=None)

def update_scheduler_table(req_id, device_id):
    print('updating scheduler table')
    query = get_update_scheduler_query(req_id, device_id)
    print(query)
    try:
        edge.api_request(db_api_url, "post", query)
        print('Successfully updated scheduler table')
    except Exception as exception:
        print('Failed to update scheduler table')
        return edge.server_error(str(exception))


def get_update_scheduler_query(req_id, device_id):
    scheduler = Table('da_edge_olympus.scheduler')
    query = Query.update(scheduler).set(scheduler.status, 'Data Rx in progress').where(scheduler.request_id == req_id
                                                                                       ).where(scheduler.device_id == device_id
                                                                                       ).where(scheduler.status == 'Config Accepted')