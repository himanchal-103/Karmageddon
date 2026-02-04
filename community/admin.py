from django.contrib import admin
from .models import Post, PostLike, Comment, CommentLike

# Register your models here.
admin.site.register(Post)
admin.site.register(PostLike)
admin.site.register(Comment)
admin.site.register(CommentLike)