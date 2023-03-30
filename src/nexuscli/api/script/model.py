from nexuscli import exception, nexus_util
from nexuscli.api import util
from nexuscli.api.base_collection import BaseCollection
from nexuscli.api.base_model import BaseModel


class ScriptCollection(BaseCollection):
    """A class to manage Nexus 3 scripts."""
    def exists(self, name):
        """
        Check if a script exists.

        :param name: of script to verify existence.
        :return: True if it exists, false otherwise
        :rtype: bool
        :raises exception.NexusClientAPIError: if the response from the Nexus
            service isn't recognised; i.e.: any HTTP code other than 200, 404.
        """
        resp = self._http.head(f'script/{name}')
        if resp.status_code == 200:
            return True
        elif resp.status_code == 404:
            return False
        else:
            if resp.content:
                raise exception.NexusClientAPIError(resp.content)
            else:
                raise exception.NexusClientAPIError(f'verify {name} existence fail: {resp.reason}, {resp.status_code}')


    def get(self, name):
        """
        Get a Nexus 3 script by name.

        :param name: of script to be retrieved.
        :return: the script or None, if not found
        :rtype: dict, None
        :raises exception.NexusClientAPIError: if the response from the Nexus
            service isn't recognised; i.e.: any HTTP code other than 200, 404.
        """
        resp = self._http.get(f'script/{name}')
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 404:
            return None
        else:
            raise exception.NexusClientAPIError(resp.content)

    def raw_list(self):
        return self._service_get('script')

    def create_if_missing(self, name, content=None, script_type='groovy'):
        """
        Creates a script in the Nexus 3 service IFF a script with the same name
        doesn't exist. Equivalent to checking if the script exists with
        :meth:`get` and, if not, creating it with :meth:`create`.

        :param name: name of script to be created.
        :type name: str
        :param content: script code. If not given, the method will use
            :py:meth:`nexuscli.nexus_util.groovy_script` to read the script
            code from a local file.
        :type content: Union[str,NoneType]
        :param script_type: type of script to be created.
        :type script_type: str
        :raises exception.NexusClientAPIError: if the script creation isn't
            successful; i.e.: any HTTP code other than 204.
        """
        content = content or nexus_util.groovy_script(name)

        if not self.exists(name):
            self.create(name, content, script_type)

    def create(self, script_name, script_content, script_type='groovy'):
        """
        Create the given script in the Nexus 3 service.

        :param script_name: name of script to be created.
        :type script_name: str
        :param script_content: script code.
        :type script_content: str
        :param script_type: type of script to be created.
        :type script_type: str
        :raises exception.NexusClientAPIError: if the script creation isn't
            successful; i.e.: any HTTP code other than 204.
        """
        script = {
            'type': script_type,
            'name': script_name,
            'content': script_content,
        }

        resp = self._http.post('script', json=script)
        util.validate_response(resp, 204)

    def run(self, *args, **kwargs):
        """See :py:meth:`run_script` """
        return self.run_script(*args, **kwargs)

    def delete(self, script_name):
        """
        Deletes a script from the Nexus 3 repository.

        :param script_name: name of script to be deleted.
        :raises exception.NexusClientAPIError: if the Nexus service fails to
            delete the script; i.e.: any HTTP code other than 204.
        """
        endpoint = f'script/{script_name}'
        resp = self._http.delete(endpoint)
        util.validate_response(resp, 204)


# TODO: describe script and use/return from collection methods
class Script(BaseModel):
    """A Class representing a Nexus 3 script."""
    pass
