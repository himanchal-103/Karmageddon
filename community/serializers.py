from rest_framework import serializers
from .models import Post, PostLike, Comment, CommentLike


# For Posts
class PostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        fields = ['id', 'author', 'title', 'body', 'created_at']
        read_only_fields = ['id', 'author', 'created_at']


# For Comments
class RecursiveCommentSerializer(serializers.Serializer):
    def to_representation(self, value):
        serializer = CommentSerializer(value, context=self.context)
        return serializer.data

class CommentSerializer(serializers.ModelSerializer):
    author = serializers.StringRelatedField(read_only=True)
    children = RecursiveCommentSerializer(many=True, read_only=True)

    class Meta:
        model = Comment
        fields = [ 'id', 'post', 'author', 'parent', 'body', 'created_at', 'children']
        read_only_fields = ['id', 'post', 'author', 'created_at', 'children']


# For postlike
class PostLikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostLike
        fields = ['id']

# For commentlike
class CommentLikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommentLike
        fields = ['id']

