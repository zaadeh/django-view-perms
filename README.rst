Automatically create and check dedicated permissions for all Django views

This Django app can create a dedicated permission for any or all
views in a given app, manage their lifecycle (exclude some views,
remove them all or remove the ones that no longer have an associated
view) and also enforce the created permissions for the logged-in
user. Users will only be able to process the views that they have
been explicitly given the related permission to.

After adding ``view_perms`` to the ``INSTALLED_APPS`` list, use the
``create_view_perms`` Django management command to create all target
permissions automatically. Permissions need to be created before
being enforced. See the command help message for details about
supported options.

To automatically enforce the created view permissions, add
``view_perms.middleware.check_view_perms.ViewPermissionMiddleware``
to the ``MIDDLEWARE`` list in Django settings. Make sure to put this
middleware after ``django.contrib.auth.middleware.AuthenticationMiddleware``.

It is possible to put some views in an ignore list, which results in them
not having the permission created or enforced. This makes sense for parts of
the application like authentication views (user needs *some* way to
authenticate, after all), or for public-facing parts of the application.
To do so add the fully qualified view name in ``VIEW_PERMS_IGNORE_LIST``
list in the Django settings module. This app enforces the views
on a per-app basis and does not enforce view permissions for views
that do not have a permission to their name (it's permissive by
default). So it's possible to have apps that none of their views are
permission enforced.

Names of permissions that this app created (ones which are displayed
in Django admin interface) are composed of a configurable prefix
(by default ``access_view_``) and the fully qualified view name
(module name + ``.`` + view function or class name).
If these names are too cryptic for users of the admin interface
or you want them to be in a local language, it has been made
possible for the programmer to provide a translation for this string by
assigning the proper ``gettext`` translation to the ``__name_trans__``
attribute of the view function or class.

