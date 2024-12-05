import os
from urllib.parse import urlparse

from web3 import Web3
from web3 import HTTPProvider, IPCProvider
from web3._utils.request import make_post_request

# Notice: to be replaced with your own endpoint
ENDPOINT_URI = ''
DEFAULT_TIMEOUT = 600

class RetriableValueError(ValueError):
    pass

# Mostly copied from web3.py/providers/rpc.py. Supports batch requests.
# Will be removed once batch feature is added to web3.py https://github.com/ethereum/web3.py/issues/832
class BatchHTTPProvider(HTTPProvider):

    def make_batch_request(self, text):
        self.logger.debug("Making request HTTP. URI: %s, Request: %s",
                          self.endpoint_uri, text)
        request_data = text.encode('utf-8')
        raw_response = make_post_request(
            self.endpoint_uri,
            request_data,
            **self.get_request_kwargs()
        )
        response = self.decode_rpc_response(raw_response)
        return response

def get_rpc_provider_from_uri(uri_string=ENDPOINT_URI, timeout=DEFAULT_TIMEOUT, batch=False):
    uri = urlparse(uri_string)
    if uri.scheme == 'http' or uri.scheme == 'https':
        request_kwargs = {'timeout': timeout}
        if batch:
            return BatchHTTPProvider(uri_string, request_kwargs=request_kwargs)
        else:
            return HTTPProvider(uri_string, request_kwargs=request_kwargs)
    else:
        raise ValueError('Unknown uri scheme {}'.format(uri_string))

def get_tracer_by_path(tracer_path:str):
    if tracer_path and os.path.exists(tracer_path):
        return open(tracer_path).read()
    else:
        return None

# for batch usage
def generate_json_rpc(method, params, request_id=1):
    return {
        'jsonrpc': '2.0',
        'method': method,
        'params': params,
        'id': request_id,
    }

def generate_geth_traces_by_transaction_hash_json_rpc(transaction_hashes, tracer=None):
    for idx, tx_hash in enumerate(transaction_hashes):
        yield generate_json_rpc(
            method='debug_traceTransaction',
            params=[tx_hash, {"tracer": get_tracer_by_path(tracer)}],
            request_id=idx
        )

def generate_traces_by_transaction_hash_json_rpc(transaction_hashes, tracer=None):
    provider = HTTPProvider(
        ENDPOINT_URI,
        request_kwargs={"timeout":DEFAULT_TIMEOUT}
    )
    w3 = Web3(provider)
    for transaction_hash in transaction_hashes:
        yield w3.manager.request_blocking("debug_traceTransaction",
                                        [transaction_hash, {"tracer": get_tracer_by_path(tracer)}])


def is_retriable_error(error_code):
    if error_code is None:
        return False

    if not isinstance(error_code, int):
        return False

    # https://www.jsonrpc.org/specification#error_object
    if error_code == -32603 or (-32000 >= error_code >= -32099):
        return True

    return False
  
def rpc_response_batch_to_results(response):
    for response_item in response:
        yield rpc_response_to_result(response_item)
        
def rpc_response_to_result(response):
    result = response.get('result')
    if result is None:
        error_message = 'result is None in response {}.'.format(response)
        if response.get('error') is None:
            error_message = error_message + ' Make sure Ethereum node is synced.'
            # When nodes are behind a load balancer it makes sense to retry the request in hopes it will go to other,
            # synced node
            raise RetriableValueError(error_message)
        elif response.get('error') is not None and is_retriable_error(response.get('error').get('code')):
            raise RetriableValueError(error_message)
        raise ValueError(error_message)
    return result

if __name__ == "__main__":
    print(Web3.keccak(hex="withdraw(uint256)"))