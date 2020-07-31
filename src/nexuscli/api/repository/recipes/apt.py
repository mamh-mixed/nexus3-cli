from nexuscli.api.repository.recipes.base import Repository
from nexuscli.api.repository.recipes.base_hosted import HostedRepository
from nexuscli.api.repository.recipes.base_proxy import ProxyRepository

__all__ = ['AptHostedRepository', 'AptProxyRepository', 'AptGroupRepository']


class _AptRepository(Repository):
    DEFAULT_RECIPE = 'apt'
    RECIPES = ('apt',)

    def __init__(self, name,
                 distribution='bionic',
                 **kwargs):
        self.distribution = distribution
        kwargs.update({'recipe': 'apt'})
        super().__init__(name, **kwargs)

    @property
    def configuration(self):
        repo_config = super().configuration

        repo_config['attributes'].update({
            'apt': {
                'distribution': self.distribution,
            }
        })

        return repo_config


class AptHostedRepository(_AptRepository, HostedRepository):
    def __init__(self, name,
                 gpg_keypair: str = None,
                 passphrase=None,
                 **kwargs):
        self.gpg_keypair = gpg_keypair
        self.passphrase = passphrase
        super().__init__(name, **kwargs)

    @property
    def configuration(self):
        repo_config = super().configuration
        repo_config['attributes'].update({
            'aptSigning': {
                'keypair': self.gpg_keypair,
                'passphrase': self.passphrase
            }
        })

        return repo_config


class AptProxyRepository(_AptRepository, ProxyRepository):
    def __init__(self, name,
                 flat=False,
                 **kwargs):
        self.flat = flat
        super().__init__(name, **kwargs)

    @property
    def configuration(self):
        repo_config = super().configuration

        repo_config['attributes']['apt']['flat'] = self.flat

        return repo_config


class AptGroupRepository:
    def __init__(self):
        raise NotImplementedError
