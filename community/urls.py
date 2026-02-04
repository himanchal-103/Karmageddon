from django.urls import path
from .views import PostViewSet, CommentViewSet, PostLikeToggleViewSet, CommentLikeToggleViewSet, UserKarmaView, UpdateKarmaCacheView


# Posts
post_list_create = PostViewSet.as_view({
    'get': 'retrieve', 
    'post': 'create',
    })

post_update_delete = PostViewSet.as_view({
    'put': 'update',
    'delete': 'destroy',
})

# Comments
comment_list_create = CommentViewSet.as_view({
    'get': 'list',
    'post': 'create',
})

comment_update_delete = CommentViewSet.as_view({
    'put': 'update',
    'delete': 'destroy',
})

# Post like/unlike
post_like_toggle = PostLikeToggleViewSet.as_view({
    'post': 'create'
})

# Comment like/unlike
comment_like_toggle = CommentLikeToggleViewSet.as_view({
    'post': 'create'
})


urlpatterns = [
    # Posts methods
    path('posts', post_list_create, name = 'post-list-create'),
    path('posts/<int:post_id>', post_update_delete, name = 'post-update-delete'),

    # Comments methods
    path('posts/<int:post_id>/comments', comment_list_create, name = 'comment-list-create'),
    path('comments/<int:comment_id>', comment_update_delete, name = 'comment-update-delete'),

    # Post and Comment like/unlike
    path('posts/<int:post_id>/like', post_like_toggle, name='post-like'),
    path('comments/<int:comment_id>/like', comment_like_toggle, name='comment-like'),

    path('karma', UserKarmaView.as_view(), name='user-karma'),
    path('karma/update-cache', UpdateKarmaCacheView.as_view(), name='update-karma-cache'),
]

