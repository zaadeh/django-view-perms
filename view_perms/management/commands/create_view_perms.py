# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

import logging
from importlib import import_module

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import CommandError
from django.core.management.base import AppCommand
from django.urls import RegexURLPattern, RegexURLResolver
from django.utils import timezone, translation
from django.utils.translation import ugettext_lazy

logger = logging.getLogger(__name__)
root_urlconf = import_module(settings.ROOT_URLCONF)  # import root_urlconf module
all_urlpatterns = root_urlconf.urlpatterns  # project's urlpatterns


def get_all_views(urlpatterns):
    """
    Return the list of all view callbacks in a URL pattern.

    This function works recursively on the given url pattern
    """
    assert isinstance(urlpatterns, (RegexURLPattern, RegexURLResolver))

    view_funcs = []
    for pattern in urlpatterns:
        if isinstance(pattern, RegexURLResolver):
            view_funcs.extend(get_all_views(pattern.url_patterns))
        # TODO: what about the new `path()` url patterns?
        elif isinstance(pattern, RegexURLPattern):
            if pattern.callback:  # if it points to a view
                view_func = pattern.callback
                view_funcs.append(view_func)

    # view_funcs = [item for item in get_resolver(None).reverse_dict.keys() if callable(item)]
    view_funcs = list(set(view_funcs))
    # TODO: sort the list by callback full name
    # view_funcs.sort()
    return view_funcs


def get_view_name(view_func):
    """
    Return the fully qualified name of the view function or class
    """

    if hasattr(view_func, 'view_class'):
        # A class-based view
        view_path = '.'.join(
            [view_func.view_class.__module__, view_func.view_class.__name__]
        )
    else:
        # A function-based view
        view_path = '.'.join([view_func.__module__, view_func.__name__])
    return view_path


class Command(AppCommand):
    """
    This command creates permissions for all view endpoints
    """

    help = "Create a permission for every view endpoint in a app, if not exist"
    missing_args_message = ""
    requires_migrations_checks = True
    requires_system_checks = True

    start_time = None

    def execute(self, *args, **options):
        self.start_time = timezone.localtime()
        logger.info("started at {}".format(self.start_time))
        if options['verbosity'] > 1:
            self.stdout.write(
                self.style.WARNING("started at {}".format(self.start_time))
            )

        retval = super(Command, self).execute(*args, **options)

        logger.info(
            "finished at {}, took {}".format(
                timezone.localtime(), timezone.localtime() - self.start_time
            )
        )
        if options['verbosity'] > 1:
            self.stdout.write(
                self.style.WARNING(
                    "finished at {}, took {}".format(
                        timezone.localtime(), timezone.localtime() - self.start_time
                    )
                )
            )
        return retval

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument(
            '--perm-prefix',
            action='store',
            dest='perm_prefix',
            default='access_view_',
            help='Specifies the prefix to add before permission code name',
        )
        parser.add_argument(
            '--language',
            action='store',
            dest='language',
            default=settings.LANGUAGE_CODE,
            help='Specifies the language to translate permission names. Default is settings.LANGUAGE_CODE.',
        )
        # TODO: add an option (--update-trans) which reads the updated
        # translation of names and updates permission names accordingly.
        parser.add_argument(
            '--update-trans',
            action='store_true',
            dest='update_trans',
            default=False,
            help='Read the updated translation for permission name and update accordingly',
        )
        parser.add_argument(
            '--delete-perms',
            action='store_true',
            dest='delete_perms',
            default=False,
            help='Remove all view permissions that have been previously created',
        )
        parser.add_argument(
            '--prune-stale',
            action='store_true',
            dest='prune_stale',
            default=False,
            help='Remove stale permissions which do not have a corresponding view and are no longer necessary',
        )

    def handle_app_config(self, app_config, **options):
        verbosity = options['verbosity']
        language = options['language']
        delete_perms = options['delete_perms']
        prune_stale = options['prune_stale']
        perm_prefix = options['perm_prefix']

        if verbosity >= 1:
            self.stdout.write("Trying to set the language to '{}'".format(language))
        translation.activate(language)
        if verbosity >= 1:
            self.stdout.write("Language set to '{}'".format(translation.get_language()))

        all_views = get_all_views(all_urlpatterns)
        # app_views = [view for view in all_views if view.__module__.startswith(app_config.name)]
        # app_views.sort(key=lambda x: '{}.{}'.format(x.__module__, x.__name__))

        app_views = []
        for view_func in all_views:
            view_name = get_view_name(view_func)
            if view_name.startswith(app_config.name):
                app_views.append(view_func)

        if verbosity >= 0:
            self.stdout.write(
                "Total of {} views found, {} of which belong in app '{}'".format(
                    len(all_views), len(app_views), app_config.name
                )
            )

        # each django permission needs to be related to a model (content_type)
        # we decided to assign django user model to the view permissions
        try:
            content_type = ContentType.objects.get_for_model(get_user_model())
        except (ContentType.DoesNotExist, ContentType.MultipleObjectsReturned) as e:
            raise CommandError("Error when finding user content type: '{}'".format(e))

        if delete_perms:
            try:
                perms = Permission.objects.filter(
                    content_type=content_type,
                    codename__startswith='{}{}.'.format(perm_prefix, app_config.name),
                )
                perm_count = len(perms)
                perms.delete()

                if verbosity >= 0:
                    self.stdout.write("{} permissions deleted".format(perm_count))
                return
            except Exception as e:
                raise CommandError("{}".format(e))

        if prune_stale:
            perm_count = 0

            try:
                perms = Permission.objects.filter(
                    content_type=content_type,
                    codename__startswith='{}{}.'.format(perm_prefix, app_config.name),
                )
                app_view_names = [
                    '{}{}'.format(perm_prefix, get_view_name(view_func))
                    for view_func in app_views
                ]

                if verbosity >= 2:
                    self.stdout.write(
                        "Currently {} view access permissions for app '{}' exist".format(
                            len(perms), app_config.name
                        )
                    )

                for perm in perms:
                    if perm.codename not in app_view_names:
                        if verbosity >= 1:
                            self.stdout.write(
                                "View access permission is no longer necessary. '{}'".format(
                                    perm.codename
                                )
                            )
                        perm.delete()
                        perm_count += 1

                if verbosity >= 0:
                    self.stdout.write("{} permissions deleted".format(perm_count))
                return
            except Exception as e:
                raise CommandError("{}".format(e))

        try:
            perm_count = 0

            for view_func in app_views:
                view_name = get_view_name(view_func)
                perm_codename = '{}{}'.format(perm_prefix, view_name)

                # TODO: support both an include and exclude list, mutually exclusive.
                # TODO: support glob patterns in include and exclude lists.
                if view_name in getattr(settings, 'VIEW_PERMS_IGNORE_LIST', []):
                    if verbosity >= 1:
                        self.stdout.write(
                            "View access permission ignored for '{}'".format(view_name)
                        )
                        # Delete if it's in ignore list
                        try:
                            Permission.objects.get(codename=perm_codename).delete()
                            self.stdout.write(
                                "Deleted view access permission for '{}', since it was in the ignore list".format(
                                    view_name
                                )
                            )
                        except Permission.DoesNotExist:
                            pass
                    continue

                # TODO: If a view is CBV, add permission for each http
                # method that it supports, if asked by the user.

                view_name_trans = view_name  # translated view name
                if hasattr(view_func, 'view_class'):
                    if hasattr(view_func.view_class, '__name_trans__'):
                        view_name_trans = view_func.view_class.__name_trans__
                elif hasattr(view_func, '__name_trans__'):
                    view_name_trans = view_func.__name_trans__

                perm_name = ugettext_lazy("Can access view %(view_name)s") % {
                    'view_name': view_name_trans
                }

                try:
                    perm = Permission.objects.get(
                        content_type=content_type, codename=perm_codename
                    )
                    if perm:
                        if verbosity >= 1:
                            self.stdout.write(
                                "View access permission already exists for '{}'".format(
                                    view_name
                                )
                            )

                        # Update perm name if it exists
                        perm.name = perm_name
                        perm.save()
                        self.stdout.write(
                            "Updated access permission name for '{}'.".format(view_name)
                        )
                except Permission.MultipleObjectsReturned:
                    raise CommandError("This should not happen")
                except Permission.DoesNotExist:
                    Permission.objects.create(
                        content_type=content_type,
                        codename=perm_codename,
                        name=perm_name,
                    )
                    if verbosity >= 1:
                        self.stdout.write(
                            "View access permission created for '{}'".format(view_name)
                        )
                    perm_count += 1

            if verbosity >= 0:
                self.stdout.write("{} permissions created".format(perm_count))
            return
        except (ValueError, IOError) as e:
            raise CommandError('\n'.join(e.messages))
