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

