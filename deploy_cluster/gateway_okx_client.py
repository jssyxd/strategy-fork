# -*- coding: utf-8 -*-
import os, sys, time, json, urllib.request, urllib.parse, hmac, hashlib, base64
from typing import Dict, Any, List, Optional

class OKXGatewayClient:
    def __init__(self, api_key: str, api_secret: str, passphrase: str, simulated: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.simulated = simulated
        self.base_url = "https://www.okx.com"

    def _sign_and_request(self, method: str, endpoint: str, params: Optional[Dict] = None, body: Optional[Dict] = None) -> Dict[str, Any]:
        request_path = endpoint
        if params:
            query_str = urllib.parse.urlencode(params)
            request_path = f"{endpoint}?{query_str}"
        url = f"{self.base_url}{request_path}"

        ts = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
        body_str = json.dumps(body) if body else ""
        msg = f"{ts}{method}{request_path}{body_str}"
        sig = base64.b64encode(hmac.new(self.api_secret.encode('utf-8'), msg.encode('utf-8'), hashlib.sha256).digest()).decode('utf-8')

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) NautilusTrader/1.221',
            'Content-Type': 'application/json',
            'OK-ACCESS-KEY': self.api_key,
            'OK-ACCESS-SIGN': sig,
            'OK-ACCESS-TIMESTAMP': ts,
            'OK-ACCESS-PASSPHRASE': self.passphrase,
        }
        if self.simulated:
            headers['x-simulated-trading'] = '1'

        data_bytes = body_str.encode('utf-8') if body else None
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=12) as resp:
            return json.loads(resp.read().decode('utf-8'))

    def get_ticker(self, inst_id: str) -> Dict[str, Any]:
        res = self._sign_and_request('GET', '/api/v5/market/ticker', {'instId': inst_id})
        data = res.get('data', [])
        return data[0] if data else {}

    def get_books(self, inst_id: str, sz: int = 20) -> Dict[str, Any]:
        res = self._sign_and_request('GET', '/api/v5/market/books', {'instId': inst_id, 'sz': str(sz)})
        data = res.get('data', [])
        return data[0] if data else {}

    def get_candles(self, inst_id: str, bar: str = '15m', limit: int = 100) -> List[List[str]]:
        res = self._sign_and_request('GET', '/api/v5/market/candles', {'instId': inst_id, 'bar': bar, 'limit': limit})
        return res.get('data', [])

    def get_balance(self, ccy: str = 'USDT') -> Dict[str, Any]:
        res = self._sign_and_request('GET', '/api/v5/account/balance', {'ccy': ccy})
        data = res.get('data', [])
        if data:
            details = data[0].get('details', [])
            if details:
                return details[0]
            return data[0]
        return {}

    def get_positions(self, inst_type: str = 'SWAP', inst_id: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {'instType': inst_type}
        if inst_id:
            params['instId'] = inst_id
        res = self._sign_and_request('GET', '/api/v5/account/positions', params)
        return res.get('data', [])

    def place_order(self, inst_id: str, td_mode: str, side: str, ord_type: str, sz: str, px: Optional[str] = None, cl_ord_id: Optional[str] = None) -> Dict[str, Any]:
        body = {
            'instId': inst_id,
            'tdMode': td_mode,
            'side': side,
            'ordType': ord_type,
            'sz': sz
        }
        if px:
            body['px'] = px
        if cl_ord_id:
            body['clOrdId'] = cl_ord_id
        return self._sign_and_request('POST', '/api/v5/trade/order', body=body)

    def cancel_order(self, inst_id: str, ord_id: Optional[str] = None, cl_ord_id: Optional[str] = None) -> Dict[str, Any]:
        body = {'instId': inst_id}
        if ord_id:
            body['ordId'] = ord_id
        if cl_ord_id:
            body['clOrdId'] = cl_ord_id
        return self._sign_and_request('POST', '/api/v5/trade/cancel-order', body=body)

    def get_pending_orders(self, inst_type: str = 'SWAP', inst_id: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {'instType': inst_type}
        if inst_id:
            params['instId'] = inst_id
        res = self._sign_and_request('GET', '/api/v5/trade/orders-pending', params)
        return res.get('data', [])
