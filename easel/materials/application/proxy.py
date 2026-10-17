"""Explicit loopback HTTP CONNECT with a public-address HTTPS DNS resolver.

The proxy can connect only to a *validated numeric public IP*. TLS/SNI and
HTTP Host remain the original allowlisted media hostname. Proxy-managed
Fake-IP DNS is never treated as an authoritative public destination.
"""
from __future__ import annotations

import http.client
import ipaddress
import json
import ssl
from urllib.parse import urlsplit

import httpx

from .acquisition import AcquisitionError, DownloadResponse


def loopback_proxy(raw: str) -> tuple[str, int]:
    try:
        parsed=urlsplit(raw)
        if (parsed.scheme!='http' or parsed.hostname not in {'127.0.0.1','::1'}
                or parsed.username is not None or parsed.password is not None
                or parsed.path not in {'','/'} or parsed.query or parsed.fragment
                or parsed.port is None or not 1 <= parsed.port <= 65535):
            raise ValueError
        return parsed.hostname, parsed.port
    except ValueError as exc:
        raise ValueError('Material proxy must be an explicit localhost HTTP CONNECT endpoint') from exc


class PublicDNSOverProxy:
    """HTTPS/CA-validated DNS-over-HTTPS via the explicitly trusted loopback proxy.

    Cloudflare's fixed numeric DoH endpoint avoids proxy DNS bootstrap cycles.
    Query/answer are bounded; only global address records are returned.
    """

    endpoint='https://1.1.1.1/dns-query'
    def __init__(self, proxy_url: str, *, transport=None, timeout: float=12):
        loopback_proxy(proxy_url)
        self.proxy_url,self.transport,self.timeout=proxy_url,transport,timeout

    def __call__(self, host: str, port: int) -> tuple[str,...]:
        if port!=443 or not isinstance(host,str) or not host or len(host)>253:
            raise AcquisitionError('Invalid public DNS query')
        try:
            with httpx.Client(proxy=self.proxy_url if self.transport is None else None,
                    transport=self.transport,trust_env=False,follow_redirects=False,
                    timeout=self.timeout) as client:
                response=client.get(self.endpoint,params={'name':host,'type':'A'},
                                    headers={'Accept':'application/dns-json'})
            if response.status_code!=200 or len(response.content)>16384:
                raise AcquisitionError('Trusted public DNS lookup unavailable')
            payload=response.json()
            if not isinstance(payload,dict) or payload.get('Status')!=0:
                raise AcquisitionError('Trusted public DNS lookup unavailable')
            questions=payload.get('Question')
            if (not isinstance(questions,list) or len(questions)!=1
                    or not isinstance(questions[0],dict)
                    or str(questions[0].get('name','')).rstrip('.').lower()!=host.lower()
                    or questions[0].get('type')!=1):
                raise AcquisitionError('Trusted public DNS query identity mismatch')
            ips=[]
            for answer in payload.get('Answer',[]):
                if not isinstance(answer,dict) or answer.get('type')!=1:
                    continue
                addr=ipaddress.ip_address(answer.get('data',''))
                if addr.version!=4 or not addr.is_global or addr.is_reserved:
                    raise AcquisitionError('Trusted DNS includes a non-public media address')
                ips.append(str(addr))
            if not ips:
                raise AcquisitionError('Trusted public DNS returned no eligible address')
            return tuple(sorted(set(ips)))[:8]
        except AcquisitionError:
            raise
        except (httpx.HTTPError,ValueError,TypeError,KeyError,json.JSONDecodeError):
            raise AcquisitionError('Trusted public DNS lookup unavailable') from None


class _ProxyPinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self,proxy_host,proxy_port,target_ip,origin_host,timeout):
        super().__init__(proxy_host,port=proxy_port,timeout=timeout,context=ssl.create_default_context())
        self._origin_host=origin_host
        self.set_tunnel(target_ip,443)
    def connect(self):
        # HTTPConnection.connect issues CONNECT to the *numeric validated IP*.
        http.client.HTTPConnection.connect(self)
        try:
            self.sock=self._context.wrap_socket(self.sock,server_hostname=self._origin_host)
        except BaseException:
            self.sock.close()
            raise


class ProxyPinnedHttpsTransport:
    """GET through the exact loopback proxy; host is TLS verified against URL."""
    def __init__(self,proxy_url: str):
        self.proxy_host,self.proxy_port=loopback_proxy(proxy_url)

    def get(self,url: str,*,headers: dict[str,str],timeout:float,
            max_bytes:int,addresses:tuple[str,...])->DownloadResponse:
        parsed=urlsplit(url)
        if parsed.scheme!='https' or parsed.port not in (None,443) or not parsed.hostname:
            raise AcquisitionError('Only HTTPS media can use the proxy')
        host=parsed.hostname
        target=(parsed.path or '/') + (('?' + parsed.query) if parsed.query else '')
        last_error=None
        for ip in addresses:
            address=ipaddress.ip_address(ip)
            if not address.is_global or address.is_reserved:
                raise AcquisitionError('Material proxy cannot connect to non-public addresses')
            connection=_ProxyPinnedHTTPS(self.proxy_host,self.proxy_port,ip,host,timeout)
            try:
                connection.request('GET',target,headers={**headers,'Host':host})
                response=connection.getresponse()
                response_headers={key.lower():value.strip() for key,value in response.getheaders()}
                if response.status in {301,302,303,307,308}:
                    return DownloadResponse(response.status,response_headers)
                value=response_headers.get('content-length')
                if value:
                    try: size=int(value)
                    except ValueError: raise AcquisitionError('Media has invalid content length') from None
                    if size<0 or size>max_bytes:
                        raise AcquisitionError('Media exceeds configured size limit')
                body=response.read(max_bytes+1)
                if len(body)>max_bytes:
                    raise AcquisitionError('Media exceeds configured size limit')
                return DownloadResponse(response.status,response_headers,body)
            except AcquisitionError:
                raise
            except (OSError,ssl.SSLError,http.client.HTTPException) as exc:
                last_error=exc
            finally:
                connection.close()
        raise AcquisitionError('Secure material proxy connection failed') from last_error
