from django.contrib import admin

from avent2024.models import UserProfile, Enigme, Devinette, Indice, IndiceDevinette
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as AuthUserAdmin

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False

class AccountsUserAdmin(AuthUserAdmin):
    def add_view(self, *args, **kwargs):
        self.inlines =[]
        return super(AccountsUserAdmin, self).add_view(*args, **kwargs)

    def change_view(self, *args, **kwargs):
        self.inlines =[UserProfileInline]
        return super(AccountsUserAdmin, self).change_view(*args, **kwargs)


admin.site.unregister(User)
admin.site.register(User, AccountsUserAdmin)

admin.site.register(Enigme)
admin.site.register(Devinette)
admin.site.register(Indice)
admin.site.register(IndiceDevinette)