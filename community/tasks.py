from celery import shared_task
from django.utils import timezone
from django.db.models import Count
from django.core.cache import cache
from django.contrib.auth import get_user_model
from .models import PostLike, CommentLike

User = get_user_model()

@shared_task
def update_daily_karma_cache():
    today = timezone.now().date()
    
    post_karma = PostLike.objects.filter(created_at__date=today).values('user').annotate(post_count=Count('id'))
    comment_karma = CommentLike.objects.filter(created_at__date=today).values('user').annotate(comment_count=Count('id'))
    
    user_karma = {}
    for post in post_karma:
        user_karma[post['user']] = {'post_likes': post['post_count'], 'comment_likes': 0, 'total': post['post_count'] * 5}
    
    for comment in comment_karma:
        if comment['user'] in user_karma:
            user_karma[comment['user']]['comment_likes'] += comment['comment_count']
            user_karma[comment['user']]['total'] += comment['comment_count']
        else:
            user_karma[comment['user']] = {'post_likes': 0, 'comment_likes': comment['comment_count'], 'total': comment['comment_count']}
    
    # Cache top 5
    top_users = sorted(user_karma.items(), key=lambda x: x[1]['total'], reverse=True)[:5]
    cache_data = [{
        'user_id': uid,
        'username': User.objects.get(id=uid).username,
        'daily_karma': data['total'],
        'post_likes': data['post_likes'],
        'comment_likes': data['comment_likes']
    } for uid, data in top_users]
    
    cache.set('daily_karma_top5', cache_data, 300)
    cache.set('daily_karma_all', user_karma, 300)
    
    return f"Karma updated for {len(user_karma)} users"
