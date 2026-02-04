from rest_framework.views import APIView
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Post, PostLike, Comment, CommentLike
from .serializers import PostSerializer, CommentSerializer

from .tasks import update_daily_karma_cache
from django.core.cache import cache
from django.db.models import Prefetch
from datetime import timedelta
from django.utils import timezone


# Create your views here.
class PostViewSet(viewsets.ViewSet):
    queryset = Post.objects.all()
    serializer_class = PostSerializer
    permission_classes = [IsAuthenticated]
    
    def retrieve(self, request):
        """
        GET /community/posts       - Get post by user

        """
        posts = self.queryset
        author_id = request.user
        posts = posts.filter(author_id=author_id)
        serializer = self.serializer_class(posts, many=True)
        return Response(serializer.data)
    
    def create(self, request):
        """
        POST /community/posts      - Create new posts
        {
            "title": "My new Post",
            "body": "This is my post content!"
        }

        """
        serializer = self.serializer_class(data=request.data)
        print()
        if serializer.is_valid():
            serializer.save(author=request.user)
            return Response(
                {"message": "Post created successfully!"}, 
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def update(self, request, post_id=None):
        """
        PUT /community/posts/<post_id>      - Update posts (author only)
        {
            "title": "My new Post",
            "body": "This is my post content!"
        }

        """
        try:
            post = self.queryset.get(id=post_id)
            if post.author != request.user:
                return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
            serializer = self.serializer_class(post, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response({"message": "Post updated successfully!"}, status=status.HTTP_200_OK)
        except Post.DoesNotExist:
                return Response({"error": "Post not found!"}, status=status.HTTP_404_NOT_FOUND)

    def destroy(self, request, post_id=None):
        """
        DELETE /community/posts/<post_id>      - Delete (author only)

        """
        try:
            post = self.queryset.get(id=post_id)
            if post.author != request.user:
                return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
            post.delete()
            return Response({"message": "Post deleted successfully!"}, status=status.HTTP_200_OK)
        except Post.DoesNotExist:
            return Response({"error": "Post not found!"}, status=status.HTTP_404_NOT_FOUND)


class CommentViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Comment.objects.select_related('author', 'post', 'parent')

    def list(self, request, post_id=None):
        """
        GET /community/posts/<post_id>/comments        - Fetch all top-level comments for a post (with nested replies)

        """
        comments = self.queryset.filter(
            post_id=post_id,
            parent__isnull=True
        )
        serializer = CommentSerializer(comments, many=True)
        return Response(serializer.data)

    def create(self, request, post_id=None):
        """
        POST /community/posts/<post_id>/comments
        {
            "body": "This is a comment",
            "parent": 1   // optional
        }
        """
        try:
            post = Post.objects.get(id=post_id)
        except Post.DoesNotExist:
            return Response({"error": "Post not found"}, status=404)

        serializer = CommentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(
                author=request.user,
                post=post
            )
            return Response(
                {"message": "Comment added successfully"},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=400)

    def update(self, request, comment_id=None):
        """
        PUT /community/comments/<comment_id>        - Update comment (author only)
        {
            "body": "Updated comment text!"
        }

        """
        try:
            comment = self.queryset.get(id=comment_id)
        except Comment.DoesNotExist:
            return Response({"error": "Comment not found"}, status=404)

        if comment.author != request.user:
            return Response({"detail": "Forbidden"}, status=403)

        serializer = CommentSerializer(comment, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Comment updated"})
        return Response(serializer.errors, status=400)

    def destroy(self, request, comment_id=None):
        """
        DELETE /community/comments/<comment_id>     - Delete comment (author only)

        """
        try:
            comment = self.queryset.get(id=comment_id)
        except Comment.DoesNotExist:
            return Response({"error": "Comment not found"}, status=404)

        if comment.author != request.user:
            return Response({"detail": "Forbidden"}, status=403)

        comment.delete()
        return Response({"message": "Comment deleted"})
    

class PostLikeToggleViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    
    def create(self, request, post_id=None):
        """
        POST /posts/{post_id}/like      - Toggle like/unlike on post
        
        """
        try:
            post = Post.objects.get(id=post_id)
        except Post.DoesNotExist:
            return Response({"error": "Post not found"}, status=404)
        
        like, created = PostLike.objects.get_or_create(
            user=request.user, 
            post=post,
            defaults={'post': post}
        )
        
        if not created:
            like.delete()
            return Response({
                "liked": False, 
                "count": post.likes.count()
            })
        
        return Response({
            "liked": True, 
            "count": post.likes.count()
        })


class CommentLikeToggleViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    
    def create(self, request, comment_id=None):
        """
        POST /comments/{comment_id}/like        - Toggle like/unlike on comment
        
        """
        try:
            comment = Comment.objects.get(id=comment_id)
        except Comment.DoesNotExist:
            return Response({"error": "Comment not found"}, status=404)
        
        like, created = CommentLike.objects.get_or_create(
            user=request.user,
            comment=comment,
            defaults={'comment': comment}
        )
        
        if not created:
            like.delete()
            return Response({
                "liked": False,
                "count": comment.likes.count()
            })
        
        return Response({
            "liked": True,
            "count": comment.likes.count()
        })


class UserKarmaView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        today = timezone.now().date()
        
        # Current user karma (real-time)
        current_karma = self._calculate_user_karma(request.user, today)
        top_users = cache.get('daily_karma_top5', [])
        
        # Trigger cache update if missing
        if not top_users:
            update_daily_karma_cache.delay()
        
        return Response({
            'current_user': {
                'username': request.user.username,
                'daily_karma': current_karma['total'],
                'post_likes': current_karma['post_likes'],
                'comment_likes': current_karma['comment_likes'],
                'rank': self._get_user_rank(request.user.username, top_users)
            },
            'top_users': top_users,
            'date': today.strftime('%Y-%m-%d'),
            'reset_time': (today + timedelta(days=1)).strftime('%Y-%m-%d 00:00'),
            'cache_fresh': bool(top_users)
        })
    
    def _calculate_user_karma(self, user, date):
        post_count = PostLike.objects.filter(user=user, created_at__date=date).count()
        comment_count = CommentLike.objects.filter(user=user, created_at__date=date).count()
        return {
            'total': (post_count * 5) + comment_count,
            'post_likes': post_count,
            'comment_likes': comment_count
        }
    
    def _get_user_rank(self, username, top_users):
        for i, user_data in enumerate(top_users):
            if user_data['username'] == username:
                return i + 1
        return None
    

class UpdateKarmaCacheView(APIView):
    def post(self, request):
        """
        POST /karma/update-cache        - Manually refresh karma leaderboard
        
        """
        
        # Trigger Celery task immediately (fire and forget)
        task = update_daily_karma_cache.delay()
        
        return Response({
            'message': 'Karma cache update triggered successfully',
            'task_id': task.id,
            'status': 'queued'
        }, status=status.HTTP_202_ACCEPTED)