# Karmageddon
A community platform to share articles about a wide variety of topics.

### Index
1. File Structure
2. How to run locally
3. Docs

### File structure

```
├── account
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── serializers.py
│   ├── tests.py
│   ├── urls.py
│   └── views.py
├── community
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── serializers.py
│   ├── tasks.py
│   ├── tests.py
│   ├── urls.py
│   └── views.py
├── karmageddon
│   ├── __init__.py
│   ├── asgi.py
│   ├── celery.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── .gitignore
├── README.md
├── manage.py
└── requirements.txt
```

### How to run locally
```
1. Clone the repo
git clone https://github.com/himanchal-103/Karmageddon.git

2. Change directory
cd Karmageddon

3. Install requirements
pip3 install -r requirements.txt

4. Start Redis
   4.1 Macos
      # Install Redis
        brew install redis

      # Start Redis (runs in the background)
        brew services start redis

      # Stop Redis server
        brew services stop redis

5. Django
python3 manage.py runserver

6. Celery Worker  
celery -A your_project worker --loglevel=info

7. Celery Beat
celery -A your_project beat --loglevel=info

```


## Docs
### 1. To be remembered
1. This project has JWT authentication, so while testing api's, remember to add tokens.
2. The author can post multiple articles.
3. Other users in the community can comment on the post, and also nested comment is supported, like the post.
4. The celery worker will calculate the karma points and store into cache. And one call the api to get the result through the worker.
   
### 2. Nested Comments Architecture
#### Database Model
```
class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=CASCADE)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=CASCADE)  # Self-referential
    author = models.ForeignKey(User, on_delete=CASCADE)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
```
#### Key Design:
1. parent = ForeignKey('self') creates unlimited depth tree
2. Top-level: parent__isnull=True
3. Children: parent=some_comment_id

#### Efficient Serialization (No N+1 Queries)
```
class RecursiveCommentSerializer(serializers.Serializer):
    def to_representation(self, value):
        serializer = CommentSerializer(value, context=self.context)
        return serializer.data

class CommentSerializer(serializers.ModelSerializer):
    author = serializers.StringRelatedField(read_only=True)
    children = RecursiveCommentSerializer(many=True, read_only=True)  # Recursive!

    class Meta:
        model = Comment
        fields = ['id', 'post', 'author', 'parent', 'body', 'created_at', 'children']
        read_only_fields = ['id', 'author', 'created_at', 'children']

# View queryset with prefetch
queryset = Comment.objects.select_related('author', 'post', 'parent').prefetch_related(
    Prefetch('children', queryset=Comment.objects.select_related('author', 'parent'))
)
```
#### Why DB-safe:
1. select_related for FKs (author/post/parent) → 1 query
2. Prefetch('children') limits recursion depth → No infinite loops
3. Lazy serialization → Only serializes accessed children


### 3. The Math: Last 24h Leaderboard QuerySet
Exact QuerySet from Celery task:
```
today = timezone.now().date()

# Post likes (5 karma each)
post_karma = PostLike.objects.filter(
    created_at__date=today  # Last 24h
).values('user').annotate(post_count=Count('id'))

# Comment likes (1 karma each)  
comment_karma = CommentLike.objects.filter(
    created_at__date=today  # Last 24h
).values('user').annotate(comment_count=Count('id'))

# Combined: user_karma[userid] = (post_count * 5) + comment_count
# Top 5: sorted(user_karma.items(), key=lambda x: x[1]['total'], reverse=True)[:5]
```
Equivalent Raw SQL:
```
-- Post karma
SELECT user_id, COUNT(*) * 5 as karma 
FROM community_postlike 
WHERE DATE(created_at) = CURDATE() 
GROUP BY user_id;

-- Comment karma  
SELECT user_id, COUNT(*) * 1 as karma
FROM community_commentlike 
WHERE DATE(created_at) = CURDATE()
GROUP BY user_id;

-- Combine & RANK top 5
SELECT username, total_karma, RANK() OVER (ORDER BY total_karma DESC) as rank
FROM (
    SELECT user_id, SUM(karma) as total_karma
    FROM (
        SELECT user_id, COUNT(*) * 5 FROM community_postlike WHERE DATE(created_at)=CURDATE() GROUP BY user_id
        UNION ALL
        SELECT user_id, COUNT(*) * 1 FROM community_commentlike WHERE DATE(created_at)=CURDATE() GROUP BY user_id
    ) combined
    GROUP BY user_id
) ranked
JOIN auth_user ON user_id=auth_user.id
ORDER BY total_karma DESC LIMIT 5;
```


### 4. The AI Audit: Bug Fix Example
Buggy Code (AI Original)
```
# BROKEN: Caused AttributeError
"count": post.post_likes.count()  # 'Post' has no attribute 'post_likes'

# User models used related_name="likes", not "post_likes"
```

Error: AttributeError: 'Post' object has no attribute 'post_likes'.

Fixed Code
```
#CORRECT: Matches user's model related_name
"count": post.likes.count()  # Uses related_name="likes" from PostLike model
```

Root Cause: AI assumed related_name='post_likes', but the user defined:

```
class PostLike(models.Model):
    post = models.ForeignKey(Post, on_delete=CASCADE, related_name="likes")  # ← "likes"
```
