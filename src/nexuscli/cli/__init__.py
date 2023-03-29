import click
import logging
import pkg_resources

from nexuscli import LOG_LEVEL, nexus_config
from nexuscli.api.repository import collection as repository_collection
from nexuscli.api.repository import model as repository_model
from nexuscli.cli import (
    repository_options, root_commands, util, subcommand_blobstore, subcommand_repository,
    subcommand_cleanup_policy, subcommand_realm, subcommand_script, subcommand_task,
    blobstore_options)
from nexuscli.cli.constants import ENV_VAR_PREFIX

PACKAGE_VERSION = pkg_resources.get_distribution('nexus3-cli').version
CONTEXT_SETTINGS = dict(
    help_option_names=['-h', '--help'], auto_envvar_prefix=ENV_VAR_PREFIX)

logging.basicConfig(level=LOG_LEVEL)


#############################################################################
# root commands
@click.group(cls=util.AliasedGroup, context_settings=CONTEXT_SETTINGS)
@click.version_option(version=PACKAGE_VERSION, message='%(version)s')
def nexus_cli():
    pass


@nexus_cli.command()
@click.option(
    '--url', '-U', default=nexus_config.DEFAULTS['url'], prompt=True,
    help='Nexus OSS URL', show_default=True, allow_from_autoenv=True, show_envvar=True)
@click.option(
    '--username', '-u', default=nexus_config.DEFAULTS['username'], prompt=True,
    help='Nexus user', show_default=True, allow_from_autoenv=True, show_envvar=True)
@click.option(
    '--password', '-p', prompt=True, hide_input=True,
    help='Password for user', allow_from_autoenv=True, show_envvar=True)
@click.option(
    '--x509_verify/--no-x509_verify', prompt=True,
    default=nexus_config.DEFAULTS['x509_verify'], show_default=True,
    help='Verify server certificate', allow_from_autoenv=True, show_envvar=True)
def login(**kwargs):
    """Login to Nexus server, saving settings to ``~/.nexus-cli.`` and ``~/.nexus-cli.env``."""
    root_commands.cmd_login(**kwargs)


@nexus_cli.command(name='list', aliases=['ls'])
@click.argument('repository_path')
@util.with_nexus_client
def list_(ctx: click.Context, repository_path):
    """
    List all files within REPOSITORY_PATH.

    REPOSITORY_PATH must start with a repository name.
    """
    root_commands.cmd_list(ctx.obj, repository_path)


@nexus_cli.command()
@click.argument('repository_path')
@util.with_nexus_client
def delete(ctx: click.Context, repository_path):
    """
    Recursively delete all files under REPOSITORY_PATH.

    REPOSITORY_PATH must start with a repository name.
    """
    root_commands.cmd_delete(ctx.obj, repository_path)


@nexus_cli.command()
# TODO: use Path for src argument
@click.argument('src')
@click.argument('dst')
@click.option('--flatten/--no-flatten', default=False, help='Flatten DST directory structure')
@click.option('--recurse/--no-recurse', default=True, help='Process all SRC subdirectories')
@util.with_nexus_client
def upload(ctx: click.Context, **kwargs):
    """
    Upload local SRC to remote DST.  If either argument ends with a `/`, it's
    assumed to be a directory.

    DEST must start with a repository name and optionally be followed by the
    path where SRC is to be uploaded to.
    """
    root_commands.cmd_upload(ctx.obj, **kwargs)


@nexus_cli.command()
@click.argument('src')
@click.argument('dst')
@click.option('--flatten/--no-flatten', default=False, help='Flatten DEST directory structure')
@click.option('--cache/--no-cache', default=True,
              help='Do not download if a local copy is already up-to-date')
@util.with_nexus_client
def download(ctx: click.Context, **kwargs):
    """
    Download remote SRC to local DEST.  If either argument ends with a `/`,
    it's assumed to be a directory.

    SRC must start with a repository name and optionally be followed by a path
    to be downloaded.
    """
    root_commands.cmd_download(ctx.obj, **kwargs)


#############################################################################
# repository sub-commands
@nexus_cli.group(cls=util.AliasedGroup)
def repository():
    """Manage repositories."""
    pass


@repository.command(name='list')
@util.with_nexus_client
def repository_list(ctx: click.Context):
    """List all repositories."""
    subcommand_repository.cmd_list(ctx.obj)


@repository.command(name='show')
@click.argument('repository_name')
@util.with_nexus_client
def repository_show(ctx: click.Context, repository_name):
    """Show the configuration for REPOSITORY_NAME as JSON."""
    subcommand_repository.cmd_show(ctx.obj, repository_name)


@repository.command(name='delete')
@click.argument('repository_name')
@click.confirmation_option()
@util.with_nexus_client
def repository_delete(ctx: click.Context, repository_name):
    """Delete REPOSITORY_NAME (but not its blobstore)."""
    subcommand_repository.cmd_delete(ctx.obj, repository_name)


#############################################################################
# repository create sub-commands
@repository.group(cls=util.AliasedGroup, name='create')
def repository_create():
    """Create a repository."""
    pass


def _create_repository(ctx, repo_type, **kwargs) -> None:
    # every repository recipe needs these
    kwargs['recipe'] = ctx.info_name
    util.upcase_values(kwargs, ['index_type', 'layout_policy', 'version_policy', 'write_policy'])

    # these CLI options were shortened for user convenience; fix them now
    util.rename_keys(kwargs, {
        'negative_cache': 'negative_cache_enabled',
        'strict_content': 'strict_content_type_validation',
        'trust_store': 'use_trust_store_for_index_access',
    })

    subcommand_repository.cmd_create(ctx, repo_type=repo_type, **kwargs)


#############################################################################
# repository create group sub-commands
@repository_create.command(
    name='group',
    cls=util.mapped_commands({
        'recipe': [
            repository_model.BowerGroupRepository.RECIPE_NAME,
            repository_model.DockerGroupRepository.RECIPE_NAME,
            repository_model.MavenGroupRepository.RECIPE_NAME,
            repository_model.NpmGroupRepository.RECIPE_NAME,
            repository_model.NugetGroupRepository.RECIPE_NAME,
            repository_model.PypiGroupRepository.RECIPE_NAME,
            repository_model.RawGroupRepository.RECIPE_NAME,
            repository_model.RubygemsGroupRepository.RECIPE_NAME,
            repository_model.YumGroupRepository.RECIPE_NAME,
        ],
    }))
def repository_create_group():
    """Create a group repository."""
    pass


@repository_create_group.command(name='recipe')  # type: ignore
@util.add_options(repository_options.COMMON)
@click.option('--member-names', '-m', multiple=True, help='Repository name(s) to add to group. '
                                                          'Use once per member. E.g.: `-m name-a '
                                                          '-m name-b`.')
@util.with_nexus_client
def repository_create_group_recipe(ctx: click.Context, **kwargs):
    """Create group repository NAME."""
    _create_repository(ctx, 'group', **kwargs)


#############################################################################
# repository create hosted sub-commands
@repository_create.command(
    name='hosted',
    cls=util.mapped_commands({
        'apt': [repository_model.AptHostedRepository.RECIPE_NAME],
        'docker': [repository_model.DockerHostedRepository.RECIPE_NAME],
        'maven': [repository_model.MavenHostedRepository.RECIPE_NAME],
        'yum': [repository_model.YumHostedRepository.RECIPE_NAME],
        # repositories that don't need custom parameters use the generic `recipe` meta-command
        'recipe': [
            repository_model.BowerHostedRepository.RECIPE_NAME,
            repository_model.NpmHostedRepository.RECIPE_NAME,
            repository_model.NugetHostedRepository.RECIPE_NAME,
            repository_model.PypiHostedRepository.RECIPE_NAME,
            repository_model.RawHostedRepository.RECIPE_NAME,
            repository_model.RubygemsHostedRepository.RECIPE_NAME,
        ],
    }))
def repository_create_hosted():
    """Create a hosted repository."""
    pass


@repository_create_hosted.command(name='recipe')  # type: ignore
@util.add_options(repository_options.HOSTED)
@util.with_nexus_client
def repository_create_hosted_recipe(ctx: click.Context, **kwargs):
    """Create a hosted repository NAME of given recipe."""
    _create_repository(ctx, 'hosted', **kwargs)


@repository_create_hosted.command(name='apt')  # type: ignore
@util.add_options(repository_options.HOSTED)
@util.add_options(repository_options.APT)
@click.option(
    '--gpg-keypair', required=True, type=click.File(),
    default='./private.gpg.key', help='Path to GPG signing key')
@click.option('--passphrase', help='Passphrase for GPG key pair')
@util.with_nexus_client
def repository_create_hosted_apt(ctx: click.Context, **kwargs):
    """Create a hosted apt repository."""
    kwargs['gpg_keypair'] = kwargs['gpg_keypair'].read()
    _create_repository(ctx, 'hosted', **kwargs)


@repository_create_hosted.command(name='docker')  # type: ignore
@util.add_options(repository_options.HOSTED)
@util.add_options(repository_options.DOCKER)
@util.with_nexus_client
def repository_create_hosted_docker(ctx: click.Context, **kwargs):
    """Create a hosted docker repository."""
    _create_repository(ctx, 'hosted', **kwargs)


@repository_create_hosted.command(name='maven')  # type: ignore
@util.add_options(repository_options.HOSTED)
@util.add_options(repository_options.MAVEN)
@util.with_nexus_client
def repository_create_hosted_maven(ctx: click.Context, **kwargs):
    """Create a hosted maven repository."""
    _create_repository(ctx, 'hosted', **kwargs)


@repository_create_hosted.command(name='yum')  # type: ignore
@util.add_options(repository_options.HOSTED)
@click.option(
    '--depth', help='Depth where repodata folder(s) exist', default=0,
    type=click.IntRange(min=0, max=5, clamp=False))
@util.with_nexus_client
def repository_create_hosted_yum(ctx: click.Context, **kwargs):
    """Create a hosted yum repository."""
    _create_repository(ctx, 'hosted', **kwargs)


#############################################################################
# repository create proxy sub-commands
@repository_create.command(
    name='proxy',
    cls=util.mapped_commands({
        'apt': [repository_model.AptProxyRepository.RECIPE_NAME],
        'docker': [repository_model.DockerProxyRepository.RECIPE_NAME],
        'maven': [repository_model.MavenProxyRepository.RECIPE_NAME],
        'yum': [repository_model.YumProxyRepository.RECIPE_NAME],
        'recipe': [
            repository_model.BowerProxyRepository.RECIPE_NAME,
            repository_model.NpmGroupRepository.RECIPE_NAME,
            repository_model.NugetProxyRepository.RECIPE_NAME,
            repository_model.PypiProxyRepository.RECIPE_NAME,
            repository_model.RawProxyRepository.RECIPE_NAME,
            repository_model.RubygemsProxyRepository.RECIPE_NAME,
        ],
    }))
def repository_create_proxy():
    """Create proxy repository NAME."""
    pass


@repository_create_proxy.command(name='recipe')  # type: ignore
@util.add_options(repository_options.PROXY)
@util.with_nexus_client
def repository_create_proxy_recipe(ctx: click.Context, **kwargs):
    """Create a proxy repository."""
    _create_repository(ctx, 'proxy', **kwargs)


@repository_create_proxy.command(name='apt')  # type: ignore
@util.add_options(repository_options.PROXY)
@util.add_options(repository_options.APT)
@click.option(
    '--flat/--no-flat', default=False, help='Is this repository flat?')
@util.with_nexus_client
def repository_create_proxy_apt(ctx: click.Context, **kwargs):
    """Create a proxy apt repository."""
    _create_repository(ctx, 'proxy', **kwargs)


@repository_create_proxy.command(name='docker')  # type: ignore
@util.add_options(repository_options.PROXY)
@util.add_options(repository_options.DOCKER)
@click.option(
    '--index-type', help='Docker index type', default='registry',
    type=click.Choice(['registry', 'hub', 'custom'],
                      case_sensitive=False))
# TODO: enforce requirement
@click.option('--index-url', help='Required for --index-type custom')
@click.option(
    '--trust-store/--no-trust-store', default=False,
    help='Required for --index-type hub or custom')
@util.with_nexus_client
def repository_create_proxy_docker(ctx: click.Context, **kwargs):
    """Create a docker proxy repository."""
    _create_repository(ctx, 'proxy', **kwargs)


@repository_create_proxy.command(name='maven')  # type: ignore
@util.add_options(repository_options.PROXY)
@util.add_options(repository_options.MAVEN)
@util.with_nexus_client
def repository_create_proxy_maven(ctx: click.Context, **kwargs):
    """Create a maven proxy repository."""
    _create_repository(ctx, 'proxy', **kwargs)


@repository_create_proxy.command(name='yum')  # type: ignore
@util.add_options(repository_options.PROXY)
@util.with_nexus_client
def repository_create_proxy_yum(ctx: click.Context, **kwargs):
    """Create a yum proxy repository."""
    _create_repository(ctx, 'proxy', **kwargs)


#############################################################################
# cleanup_policy sub-commands
@nexus_cli.group(cls=util.AliasedGroup)
def cleanup_policy():
    """Manage clean-up policies."""
    pass


@cleanup_policy.command(name='create')
@click.argument('name')
@click.option(
    '--format', default='all',
    help='The recipe that this cleanup policy can be applied to',
    type=click.Choice(['all'] + repository_collection.get_supported_recipes()))
@click.option(
    '--downloaded', type=click.IntRange(min=1),
    help='Cleanup criteria; last downloaded in this many days.')
@click.option(
    '--updated', type=click.IntRange(min=1),
    help='Cleanup criteria; last updated in this many days.')
# TODO: validate formats that accept regex
@click.option(
    '--regex',
    help='Cleanup criteria; only cleanup components matching expression')
@click.option(
    '--notes',
    help='Notes about your policy')
@util.with_nexus_client
def cleanup_policy_create(ctx: click.Context, **kwargs):
    """Create or update a cleanup policy called NAME."""
    # TODO: use a click type for this check?
    criteria_keys = {'downloaded', 'updated', 'regex'}
    util.move_to_key(kwargs, 'criteria', criteria_keys)

    util.rename_keys(kwargs['criteria'], {
        'downloaded': 'lastDownloaded',
        'updated': 'lastBlobUpdated',
    })

    subcommand_cleanup_policy.cmd_create(ctx.obj, **kwargs)


@cleanup_policy.command(name='list')
@util.with_nexus_client
def cleanup_policy_list(ctx: click.Context):
    subcommand_cleanup_policy.cmd_list(ctx.obj)


@cleanup_policy.command(name='show')
@click.argument('policy_name')
@util.with_nexus_client
def cleanup_policy_show(ctx: click.Context, policy_name):
    """Show the details for POLICY_NAME as JSON."""
    subcommand_cleanup_policy.cmd_show(ctx.obj, policy_name)


#############################################################################
# script sub-commands
@nexus_cli.group(cls=util.AliasedGroup)
def script():
    """Manage scripts."""
    pass


@script.command(name='create')
@click.argument('name')
@click.argument('file', type=click.File())
@click.option('--script-type', default='groovy', help='Script type')
@util.with_nexus_client
def script_create(ctx: click.Context, name, file, **kwargs):
    """Create a new script called NAME from FILE."""
    subcommand_script.cmd_create(ctx.obj, name, file.read(), **kwargs)


@script.command(name='delete')
@click.argument('name')
@util.with_nexus_client
def script_delete(ctx: click.Context, name):
    """Delete the script called NAME."""
    subcommand_script.cmd_delete(ctx.obj, name)


@script.command(name='list')
@util.with_nexus_client
def script_list(ctx: click.Context):
    """List all scripts."""
    subcommand_script.cmd_list(ctx.obj)


@script.command(name='run')
@click.argument('name')
@click.option('--script-arguments', '-a')
@util.with_nexus_client
def script_run(ctx: click.Context, name, script_arguments):
    """Run the script called NAME."""
    subcommand_script.cmd_run(ctx.obj, name, script_arguments)


#############################################################################
# tasks sub-commands
@nexus_cli.group(cls=util.AliasedGroup)
def task():
    """Task operations."""
    pass


@task.command(name='list')
@click.option('--json/--no-json', default=False, help='Print output as json')
@util.with_nexus_client
def task_list(ctx: click.Context, **kwargs):
    """List all tasks."""
    subcommand_task.cmd_list(ctx.obj, **kwargs)


@task.command(name='show')
@click.argument('task_id')
@util.with_nexus_client
def task_show(ctx: click.Context, task_id):
    """Show the details for TASK_ID as JSON."""
    subcommand_task.cmd_show(ctx.obj, task_id)


@task.command(name='run')
@click.argument('task_id')
@util.with_nexus_client
def task_run(ctx: click.Context, task_id):
    """Run TASK_ID."""
    subcommand_task.cmd_run(ctx.obj, task_id)


@task.command(name='stop')
@click.argument('task_id')
@util.with_nexus_client
def task_stop(ctx: click.Context, task_id):
    """Stop running TASK_ID."""
    subcommand_task.cmd_stop(ctx.obj, task_id)


#############################################################################
# security sub-commands
@nexus_cli.group(cls=util.AliasedGroup)
def security():
    """Security operations."""
    pass


@security.group(cls=util.AliasedGroup, name='realm')
def security_realm():
    """Security realms operations."""
    pass


@security_realm.command(name='activate')
@click.argument('realm_id')
@util.with_nexus_client
def security_realm_activate(ctx: click.Context, realm_id):
    """Activate REALM_ID"""
    subcommand_realm.cmd_activate(ctx.obj, realm_id)


@security_realm.command(name='active')
@util.with_nexus_client
def security_realm_active(ctx: click.Context):
    """List active security realms as a JSON list."""
    subcommand_realm.cmd_active(ctx.obj)


@security_realm.command(name='available')
@click.option('--json/--no-json', default=False, help='Print output as json')
@util.with_nexus_client
def security_realm_available(ctx: click.Context, **kwargs):
    """List available security realms."""
    subcommand_realm.cmd_available(ctx.obj, **kwargs)


#############################################################################
# blobstore sub-commands
@nexus_cli.group(cls=util.AliasedGroup)
def blobstore():
    """Blob store operations."""
    pass


@blobstore.command(name='list')
@click.option('--json/--no-json', default=False, help='Print output as json')
@util.with_nexus_client
def blobstore_list(ctx: click.Context, **kwargs):
    """List all blob stores."""
    subcommand_blobstore.cmd_list(ctx.obj, **kwargs)


@blobstore.command(name='show')
@click.argument('name')
@util.with_nexus_client
def blobstore_show(ctx: click.Context, name):
    """Show the details for NAME as JSON."""
    subcommand_blobstore.cmd_show(ctx.obj, name)


@blobstore.command(name='delete')
@click.argument('name')
@click.confirmation_option()
@util.with_nexus_client
def blobstore_delete(ctx: click.Context, name):
    """Delete blob store NAME"""
    subcommand_blobstore.cmd_delete(ctx.obj, name)


@blobstore.group(cls=util.AliasedGroup, name='create')
def blobstore_create():
    """Create a new Blobstore."""
    pass


@blobstore_create.command(name='file')
@util.add_options(blobstore_options.COMMON)
@click.argument('path')
@util.with_nexus_client
def blobstore_create_file(ctx: click.Context, name, path, **kwargs):
    """Create NAME blob store of type File stored at PATH."""
    subcommand_blobstore.cmd_create(ctx.obj, 'File', name, path=path, **kwargs)


@blobstore_create.command(name='s3')
@util.add_options(blobstore_options.S3)
@util.add_options(blobstore_options.COMMON)
@util.with_nexus_client
def blobstore_create_s3(ctx: click.Context, name, **kwargs):
    """Create NAME blob store of type S3."""
    subcommand_blobstore.cmd_create(ctx.obj, 'S3', name, **kwargs)
