import hashlib
import logging
import mmap
import os
import pathlib
import pkg_resources
from typing import Tuple

from nexuscli import exception

LOG = logging.getLogger(__name__)

REMOTE_PATH_SEPARATOR = '/'
"""The character used by the Nexus server as a path separator"""


def _resource_filename(resource_name):
    """wrapper for pkg_resources.resource_filename"""
    return pkg_resources.resource_filename('nexuscli', resource_name)


def groovy_script(script_name):
    """
    Returns the content for a groovy script located in the package installation
    path under script/groovy.

    E.g.: groovy_script('foo') returns the content for the file at
    ``.../site-packages/nexuscli/script/groovy/foo.groovy``.

    :param script_name: file name of the groovy script; ``.groovy`` is appended
        to this parameter to form the file name.
    :return: content for the groovy script
    :rtype: str
    """
    script_path = os.path.join(
        'api', 'script', 'groovy', f'{script_name}.groovy')
    script_path = _resource_filename(script_path)
    return open(script_path).read()


def validate_strings(*args):
    """
    Checks that all given arguments have a string type (e.g. str, basestring,
    unicode etc)

    Args:
        *args: values to be validated.

    Returns:
        bool: True if all arguments are of a string type. False otherwise.
    """
    for arg in args:
        if not isinstance(arg, str):
            return False

    return True


def calculate_hash(hash_name, file_path_or_handle):
    """
    Calculate a hash for the given file.

    :param hash_name: name of the hash algorithm in hashlib
    :type hash_name: str
    :param file_path_or_handle: source file name (:py:obj:`str`) or file
        handle (:py:obj:`file-like`) for the hash algorithm.
    :type file_path_or_handle: str
    :return: the calculated hash
    :rtype: str
    """
    def _hash(_fd):
        h = hashlib.new(hash_name)
        stat = os.fstat(_fd.fileno())
        if stat.st_size > 0:  # can't map a zero-length file
            m = mmap.mmap(_fd.fileno(),
                          stat.st_size, access=mmap.ACCESS_READ)
            h.update(m)
        return h.hexdigest()

    if hasattr(file_path_or_handle, 'read'):
        return _hash(file_path_or_handle)
    else:
        with open(file_path_or_handle, 'rb') as fd:
            return _hash(fd)


def has_same_hash(artefact, filepath):
    """
    Checks if a Nexus artefact has the same hash as a local filepath.

    :param artefact:  as returned by
        :py:meth:`~nexuscli.nexus_client.NexusClient.list_raw`
    :type artefact: dict
    :param filepath: local file path
    :return: True if artefact and filepath have the same hash.
    :rtype: bool
    """
    for hash_name in ['sha1', 'md5']:
        remote_hash = artefact.get('checksum', {}).get(hash_name)
        if remote_hash is None:
            continue

        local_hash = calculate_hash(hash_name, filepath)
        return local_hash == remote_hash

    return False


def ensure_exists(path: pathlib.Path, is_dir: bool = False):
    """
    Ensures a path exists.

    :param path: the path to ensure
    :type path: pathlib.Path
    :param is_dir: whether the path is a directory.
    :type is_dir: bool
    """
    LOG.debug('Creating %s, is_dir=%s', path, is_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    if is_dir:
        path.mkdir(exist_ok=True)
    else:
        path.touch()


def pop_repository(component_path):
    """
    Helper for split_component_path. Returns the repository and the
    remainder of the component_path as a path_fragments list.

    :param component_path: the component path, as given to
        split_component_path.
    :return: tuple of (repository, path_fragments)
    :rtype: tuple(str, list)
    """
    path_fragments = component_path.split(REMOTE_PATH_SEPARATOR)
    try:
        repository = path_fragments.pop(0)
        # no cheating!
        if not repository or repository == '.':
            raise IndexError
    except IndexError:
        raise exception.NexusClientInvalidRepositoryPath(
            f'The given path does not contain a repository: {component_path}')

    return repository, path_fragments


def _pop_filename(component_path, path_fragments):
    """
    Helper for split_component_path. Returns the filename.

    :param component_path: the component path, as given to
        split_component_path.
    :param path_fragments: as returned by _pop_repository.
    :return: filename or None, if not available.
    :rtype: str
    """
    filename = None
    try:
        if not component_path.endswith(REMOTE_PATH_SEPARATOR):
            filename = path_fragments.pop()
            if not filename or filename == '.':
                raise IndexError
    except IndexError:
        return None

    return filename


def _pop_directory(path_fragments):
    """
    Helper for split_component_path. Returns the directory.

    :param path_fragments: as returned by _pop_repository.
    :return: directory or None, if not available.
    :rtype: str
    """
    directory = REMOTE_PATH_SEPARATOR.join(path_fragments)
    # for consistency
    if directory.endswith(REMOTE_PATH_SEPARATOR):
        directory = directory[:-1]
    # nice try, user but no cigar
    if not directory or directory == '.':
        directory = None

    return directory


def split_component_path(component_path):
    """
    Splits a given component path into repository, directory, filename.

    A Nexus component path for a raw directory must have this format:

    ``repository_name/directory[(/subdir1)...][/|filename]``

    A path ending in ``/`` represents a directory; otherwise it represents
    a filename.

        >>> dst0 = 'myrepo0/dir/'
        >>> dst1 = 'myrepo1/dir/subdir/'
        >>> dst2 = 'myrepo2/dir/subdir/file'
        >>> dst3 = 'myrepo3/dir/subdir/etc/file.ext'
        >>> split_component_path(dst0)
        >>> ('myrepo0', 'dir', None)
        >>> split_component_path(dst1)
        >>> ('myrepo1', 'dir/subdir', None)
        >>> split_component_path(dst2)
        >>> ('myrepo2', 'dir/subdir', 'file')
        >>> split_component_path(dst3)
        >>> ('myrepo3', 'dir/subdir/etc', 'file.ext')

    :param component_path: the Nexus component path, as described above.
    :type component_path: str
    :return: tuple of ``(repository_name, directory, filename)``. If the
        given ``component_path`` doesn't represent a file, then the
        ``filename`` is set to :py:obj:`None`.
    :rtype: tuple[str, str, str]
    """
    repository, path_fragments = pop_repository(component_path)
    filename = _pop_filename(component_path, path_fragments)
    directory = _pop_directory(path_fragments)

    return repository, directory, filename


def get_dst_path_and_file(source: str, destination: str) -> Tuple[str, str]:
    """
    Given a source file and destination path, return a destination path and destination file name.

    :param source: the source file path. The name of this file is used as the returned file name
        when the given destination is a directory.
    :param destination: the destination path. When this is a path to a file, the returned
        destination is the base path of this value and the returned file name matches this one.
    """
    destination = os.path.normpath(destination or REMOTE_PATH_SEPARATOR).replace(os.sep, REMOTE_PATH_SEPARATOR)

    if destination.endswith(REMOTE_PATH_SEPARATOR):
        dst_file = os.path.basename(source)
    else:
        dst_file = os.path.basename(destination)
        destination = os.path.dirname(destination)

    return destination, dst_file


def remote_path_to_local(remote_src, local_dst, flatten, create=True):
    """
    Takes the remote path of an asset (without the repository name), the
    desired destination in the local file system, and creates the fully
    qualified path according to the instance settings.

    If self.flatten is True, the remote_path isn't reproduced locally.

    If the remote is a directory, we'll always assume the destination is
    also a directory, even if it doesn't end with a /.

    :param remote_src: path to the artefact as reported by the artefact
        service (i.e.: the `path` attribute of an asset object).
    :param local_dst: desired location in the local filesystem for the
        remote_path.
    :param create: whether or not to create the local destination file or
        directory.
    :return: the local path to be used.
    """
    # FIXME: use of multiple .. in the local_dst isn't resolved correctly
    remote_isdir = remote_src.endswith(REMOTE_PATH_SEPARATOR)
    # force destination to be a directory if the remote is a directory
    destination_isdir = (remote_isdir or
                         local_dst.endswith('.') or
                         local_dst.endswith('..') or
                         local_dst.endswith(os.sep))
    if remote_src.startswith(REMOTE_PATH_SEPARATOR):
        # remove the / starting the component path from nexus,
        # this will confuse the downloaded files to be put in root
        remote_src = remote_src[len(REMOTE_PATH_SEPARATOR):]
    local_relative = remote_src.replace(REMOTE_PATH_SEPARATOR, os.sep)
    if flatten:
        local_relative = os.path.basename(local_relative)
    # remote=file, destination=file
    if not (remote_isdir or destination_isdir):
        # if files are given, rename the source to match destination
        local_relative_dir = os.path.dirname(local_relative)
        dst_file_name = os.path.basename(local_dst)
        local_dst = os.path.dirname(local_dst)
        if flatten:
            local_relative = dst_file_name
        else:
            local_relative = os.path.join(
                local_relative_dir, dst_file_name)

    destination_path = pathlib.Path(local_dst)
    local_path = destination_path.joinpath(local_relative)

    if create:
        ensure_exists(local_path, is_dir=remote_isdir)

    return local_path.absolute()
