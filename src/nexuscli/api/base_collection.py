from typing import List, Optional, Union

from nexuscli import exception
from nexuscli.nexus_http import NexusHttp


class BaseCollection:
    """
    A base collection class that contains a Nexus 3 client.

    Args:
        nexus_http: the NexusHttp instance that will be used to perform requests against the Nexus
        service. You must provide this at instantiation if you want to call any methods that
        require connectivity to Nexus.
    """
    def __init__(self, nexus_http: NexusHttp = None):
        self._http: NexusHttp = nexus_http
        self._list: Optional[List[dict]] = None

    def script_dependencies(self) -> List[str]:
        """
        This method returns any scripts that the collection class depends on. These will be
        installed by the NexusClient instance, if not already present on the server.
        """
        return []

    def run_script(self, script_name: str, data: Union[str, dict] = ''):
        """
        Runs an existing script on the Nexus 3 service.

        :param script_name: name of script to be run.
        :param data: parameters to be passed to the script, via HTTP POST. If
            the script being run requires a certain format or encoding, you
            need to prepare it yourself. Typically this is `json.dumps(data)`.
        :return: the content returned by the script, if any.
        :rtype: str, dict
        :raises exception.NexusClientAPIError: if the Nexus service fails to
            run the script; i.e.: any HTTP code other than 200.
        """
        if self._http is None:
            raise ValueError('Instance has no client')

        if not self._http.config.groovy_enabled:
            raise exception.FeatureNotImplemented(
                f'Unable to run {script_name}: groovy_enabled is False')

        headers = {'content-type': 'text/plain'}
        endpoint = f'script/{script_name}/run'
        resp = self._http.post(endpoint, headers=headers, data=data)
        if resp.status_code != 200:
            if resp.content:
                raise exception.NexusClientAPIError(resp.content)
            else:
                raise exception.NexusClientAPIError(f'run script {script_name} fail: {resp.reason}, {resp.status_code}')

        return resp.json()

    @property
    def list(self) -> List[dict]:
        """Cached version of :py:meth:`raw_list`. Use :py:meth:`reset` to refresh."""
        if self._list is None:
            self._list = self.raw_list()
        return self._list

    def raw_list(self) -> List[dict]:
        raise NotImplementedError

    def reset(self) -> None:
        """
        Clears the cached collection and causes the next call to :py:meth:`list` to reload the
        response from the Nexus server.
        """
        self._list = None

    def _service_get(self, endpoint: str, api_version: Optional[str] = None):
        """Most implementations of :py:meth:`raw_list` will use something like this"""
        if self._http is None:
            raise AttributeError('Define a client before using this method')

        service_url = None
        if api_version is not None:
            service_url = self._http.rest_url + api_version + '/'
        resp = self._http.get(endpoint, service_url=service_url)

        if resp.status_code != 200:
            raise exception.NexusClientAPIError(resp.content)

        return resp.json()

    @staticmethod
    def _get_by_key(items: List[dict], key: str, value: str):
        """Returns the first matching item in a list of dictionaries where item[key] == value"""
        for item in items:
            try:
                if item[key] == value:
                    return item
            except KeyError:
                pass
        raise exception.NotFound(f'Item matching {key}=={value}')
