# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.urls import resolve
from django.urls.exceptions import Resolver404
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class ViewPermissionMiddleware(MiddlewareMixin):
    """
    This middleware class tries to find the view name which is about
    to be run and check whether the logged in user has been granted the
    per-view permission to access it.

    Should be placed after `django.contrib.auth` middleware.
    """

    def process_request(self, request):
        if not hasattr(request, 'user'):
            raise ImproperlyConfigured(
                "'{}' needs to be placed after django auth middleware".format(
                    self.__class__.__name__
                )
            )

        try:
            content_type = ContentType.objects.get_for_model(get_user_model())
        except (ContentType.DoesNotExist, ContentType.MultipleObjectsReturned) as e:
            raise ImproperlyConfigured(
                "Failed to find user content type: '{}'".format(e)
            )

        try:
            view = resolve(request.get_full_path())[0]
        except Resolver404:
            logger.warning(
                "path '{}' could not be resolved. not enforcing view permission".format(
                    request.get_full_path()
                )
            )
            return

        if hasattr(view, 'view_func'):
            logger.error('FIXME')  ## FIXME related to CBVs?
            view = view.view_func

        view_name = '{}.{}'.format(view.__module__, view.__name__)
        perm_prefix = getattr(settings, 'VIEW_PERMS_PREFIX', 'access_view_')
        perm_codename = '{}{}'.format(perm_prefix, view_name)

        # Permission = apps.get_model('auth', 'Permission')
        try:
            perm = Permission.objects.get(
                content_type=content_type, codename=perm_codename
            )
        except Permission.MultipleObjectsReturned:
            logger.error(
                "This should not happen: '{}', '{}'".format(content_type, perm_codename)
            )
        except Permission.DoesNotExist:
            ## TODO: also check if perm has been put in ignore list
            logger.debug(
                "permission named '{}' does not exist. not enforcing view permission".format(
                    perm_codename
                )
            )
            return

        if not request.user.is_authenticated or not request.user.has_perm(
            'auth.{}'.format(perm_codename)
        ):
            logger.debug(
                "user '{}' tried to access view '{}' without being granted access to".format(
                    request.user, view_name
                )
            )
            raise PermissionDenied()
