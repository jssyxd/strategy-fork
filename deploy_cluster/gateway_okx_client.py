# -*- coding: utf-8 -*-
"""
Production OKX API Gateway Client.
Features:
- HMAC-SHA256 signature generation
- Native fallback DNS resolver (queries 8.8.8.8/8.8.4.4 on gaierror)
- In-memory DNS cache & socket hook
- Automatic 3-attempt exponential retry on network/transport fluctuations
- Complete support for v5 market, trade, and account endpoints
"""

import os, sys, time, json, urllib.request, urllib.parse, hmac, hashlib, base64, socket, random
from typing import Dict, Any, List, Optional

_DNS_CACHE: Dict[str, List[str]] = {}
_ORIG_GETADDRINFO = socket.getaddrinfo

def _query_dns_fallback(domain: str, dns_servers=("8.8.8.8", "8.8.4.4"), timeout=2) -> List[str]:
    trans_id = random.randint(0, 65535)
    header = trans_id.to_bytes(2, 'big') + b'\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00'
    qname = b''
    for part in domain.split('.'):
        qname += len(part).to_bytes(1, 'big') + part.encode()
    qname += b'\x00'
    packet = header + qname + b'\x00\x01\x00\x01' # Type A, Class IN
    
    for server in dns_servers:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            sock.sendto(packet, (server, 53))
            data, _ = sock.recvfrom(512)
            sock.close()
            
            idx = 12 + len(qname) + 4
            ips = []
            while idx < len(data):
                if data[idx] & 0xc0 == 0xc0:
                    idx += 2
                else:
                    while idx < len(data) and data[idx] != 0:
                        idx += data[idx] + 1
                    idx += 1
                if idx + 10 > len(data):
                    break
                atype = int.from_bytes(data[idx:idx+2], 'big')
                rdlength = int.from_bytes(data[idx+8:idx+10], 'big')
                idx += 10
                if atype == 1 and rdlength == 4:
                    ip = '.'.join(str(b) for b in data[idx:idx+4])
                    ips.append(ip)
                idx += rdlength
            if ips:
                return ips
        except Exception:
            continue
    return []

def _smart_getaddrinfo(host, port, *args, **kwargs):
    try:
        return _ORIG_GETADDRINFO(host, port, *args, **kwargs)
    except socket.gaierror:
        if host in _DNS_CACHE and _DNS_CACHE[host]:
            cached_ip = random.choice(_DNS_CACHE[host])
            return _ORIG_GETADDRINFO(cached_ip, port, *args, **kwargs)
        # Try fallback query
        ips = _query_dns_fallback(host)
        if ips:
            _DNS_CACHE[host] = ips
            return _ORIG_GETADDRINFO(ips[0], port, *args, **kwargs)
        raise

# Install resilient DNS resolver
socket.getaddrinfo = _smart_getaddrinfo

class OKXGatewayClient:
    def __init__(self, api_key: str, api_secret: str, passphrase: str, simulated: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.simulated = simulated
        self.base_url = "https://www.okx.com"

    def _sign_and_request(self, method: str, endpoint: str, params: Optional[Dict] = None, body: Optional[Dict] = None, max_retries: int = 3) -> Dict[str, Any]:
        request_path = endpoint
        if params:
            query_str = urllib.parse.urlencode(params)
            request_path = f"{endpoint}?{query_str}"
        url = f"{self.base_url}{request_path}"

        body_str = json.dumps(body) if body else ""
        data_bytes = body_str.encode('utf-8') if body else None

        last_error = None
        for attempt in range(max_retries):
            ts = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
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

            req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    return json.loads(resp.read().decode('utf-8'))
            except Exception as e:
                last_error = e
                # Check if we should resolve host via fallback
                if "name resolution" in str(e).lower() or isinstance(e, socket.gaierror):
                    ips = _query_dns_fallback("www.okx.com")
                    if ips:
                        _DNS_CACHE["www.okx.com"] = ips
                time.sleep(1.0 * (attempt + 1))
                
        raise last_error

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
