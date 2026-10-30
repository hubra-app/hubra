import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, TextInput, Paper, Loader, Center } from '@mantine/core'
import {
  IconArrowLeft,
  IconHeart,
  IconMessage2,
  IconTrash,
} from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useToast, useAuth } from '@/context/AppContext'
import { PageHead, Avatar } from '@/components/ui'
import { MarkdownRenderer } from '@/components/MarkdownRenderer'
import type { Post, PostComment as PostCommentType } from '@/types'
import {
  getPost,
  likePost,
  unlikePost,
  listComments,
  addComment,
  deleteComment,
} from '@/api/posts'
import { qk } from '@/data/keys'

export function PostDetailScreen() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { t } = useT()
  const { notify } = useToast()
  const { currentUser, isAdmin, hasPermission } = useAuth()
  const queryClient = useQueryClient()

  const {
    data: post,
    isLoading: loading,
    isError,
  } = useQuery({
    queryKey: qk.posts.one(id),
    queryFn: () => getPost(id!),
    enabled: !!id,
  })
  const { data: comments = [] } = useQuery<PostCommentType[]>({
    queryKey: qk.posts.comments(id),
    queryFn: () => listComments(id!),
    enabled: !!id,
  })
  const [commentInput, setCommentInput] = useState('')
  const [submittingComment, setSubmittingComment] = useState(false)
  const canLike = hasPermission('posts.posts.like')
  const canComment = hasPermission('posts.posts.comment')
  const canModerate = hasPermission('posts.posts.moderate')

  const toggleLike = async () => {
    if (!post) return
    const liked = post.likeMemberIds.includes(currentUser?.id ?? '')
    try {
      const updated = liked
        ? await unlikePost(post.id)
        : await likePost(post.id)
      queryClient.setQueryData<Post>(qk.posts.one(id), updated)
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error ? err.message : '',
      )
    }
  }

  const submitComment = async () => {
    if (!id || !commentInput.trim()) return
    setSubmittingComment(true)
    try {
      const comment = await addComment(id, commentInput.trim())
      queryClient.setQueryData<PostCommentType[]>(
        ['post-comments', id],
        (prev) => [...(prev ?? []), comment],
      )
      queryClient.setQueryData<Post>(qk.posts.one(id), (prev) =>
        prev ? { ...prev, comments: prev.comments + 1 } : prev,
      )
      setCommentInput('')
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error ? err.message : '',
      )
    } finally {
      setSubmittingComment(false)
    }
  }

  const removeComment = async (commentId: string) => {
    if (!id) return
    try {
      await deleteComment(id, commentId)
      queryClient.setQueryData<PostCommentType[]>(
        ['post-comments', id],
        (prev) => (prev ?? []).filter((c) => c.id !== commentId),
      )
      queryClient.setQueryData<Post>(qk.posts.one(id), (prev) =>
        prev ? { ...prev, comments: prev.comments - 1 } : prev,
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error ? err.message : '',
      )
    }
  }

  if (loading) {
    return (
      <Center h={400}>
        <Loader />
      </Center>
    )
  }

  if (!post || isError) {
    return (
      <div>
        <PageHead
          title={t('posts.notFound', 'Beitrag nicht gefunden')}
          actions={
            <Button
              variant="default"
              onClick={() => navigate('/app/operations/posts')}
            >
              <IconArrowLeft size={16} />
              {t('common.back', 'Zurück')}
            </Button>
          }
        />
      </div>
    )
  }

  const liked = post.likeMemberIds.includes(currentUser?.id ?? '')

  return (
    <div>
      <PageHead
        title={post.title}
        actions={
          <Button
            variant="default"
            onClick={() => navigate('/app/operations/posts')}
          >
            <IconArrowLeft size={16} />
            {t('posts.backToPosts', 'Zurück zu den Beiträgen')}
          </Button>
        }
      />
      <Paper withBorder shadow="sm" radius="lg" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
          <Avatar name={post.author} color={post.avatarColor} size={38} />
          <div>
            <div
              style={{
                fontSize: 'var(--mantine-font-size-sm)',
                fontWeight: 600,
                color: '#1a1625',
              }}
            >
              {post.author}
            </div>
            <div
              className="num"
              style={{
                fontSize: 'var(--mantine-font-size-xs)',
                color: '#8c86a0',
              }}
            >
              {post.time}
            </div>
          </div>
        </div>
        <div
          style={{
            fontSize: 'var(--mantine-font-size-sm)',
            color: '#2e2940',
            lineHeight: 1.6,
            marginBottom: 16,
          }}
        >
          <MarkdownRenderer content={post.body} />
        </div>
        <div
          style={{
            display: 'flex',
            gap: 12,
            borderTop: '1px solid #e6e3ef',
            paddingTop: 12,
          }}
        >
          {canLike && (
            <Button
              size="sm"
              variant="subtle"
              style={{ color: liked ? '#ff4d3d' : '#5e5873' }}
              onClick={toggleLike}
            >
              <IconHeart
                size={16}
                style={{ fill: liked ? '#ff4d3d' : 'none' }}
              />
              {post.likes}
            </Button>
          )}
          <Button size="sm" variant="subtle" style={{ color: '#5e5873' }}>
            <IconMessage2 size={16} />
            {post.comments}
          </Button>
        </div>
      </Paper>

      <Paper
        withBorder
        shadow="sm"
        radius="lg"
        style={{ marginTop: 16, padding: '24px' }}
      >
        <div
          style={{
            fontSize: 'var(--mantine-font-size-sm)',
            fontWeight: 700,
            color: '#1a1625',
            marginBottom: 16,
          }}
        >
          {t('posts.comments', 'Kommentare')}
        </div>
        {comments.length === 0 ? (
          <div
            style={{
              fontSize: 'var(--mantine-font-size-xs)',
              color: '#8c86a0',
              marginBottom: 12,
            }}
          >
            {t('posts.noComments', 'Noch keine Kommentare.')}
          </div>
        ) : (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 10,
              marginBottom: 12,
            }}
          >
            {comments.map((comment) => (
              <div key={comment.id} style={{ display: 'flex', gap: 8 }}>
                <Avatar
                  name={comment.author}
                  color={comment.avatarColor}
                  size={28}
                />
                <div style={{ flex: 1 }}>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                      marginBottom: 2,
                    }}
                  >
                    <span
                      style={{
                        fontSize: 'var(--mantine-font-size-xs)',
                        fontWeight: 600,
                        color: '#1a1625',
                      }}
                    >
                      {comment.author}
                    </span>
                    <span
                      className="num"
                      style={{
                        fontSize: 'var(--mantine-font-size-xs)',
                        color: '#8c86a0',
                      }}
                    >
                      {comment.time}
                    </span>
                    {((canComment &&
                      (comment.authorId === currentUser?.id || canModerate)) ||
                      isAdmin) && (
                      <Button
                        size="compact-xs"
                        variant="subtle"
                        style={{ color: '#ff4d3d', marginLeft: 'auto' }}
                        onClick={() => removeComment(comment.id)}
                      >
                        <IconTrash size={12} />
                      </Button>
                    )}
                  </div>
                  <div
                    style={{
                      fontSize: 'var(--mantine-font-size-sm)',
                      color: '#2e2940',
                      lineHeight: 1.5,
                    }}
                  >
                    {comment.body}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
        {canComment && (
          <div style={{ display: 'flex', gap: 8 }}>
            <TextInput
              value={commentInput}
              onChange={(e) => setCommentInput(e.target.value)}
              placeholder={t('posts.commentPlaceholder', 'Schreibe einen Kommentar …')}
              style={{ flex: 1 }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  submitComment()
                }
              }}
            />
            <Button
              variant="filled"
              size="sm"
              disabled={!commentInput.trim() || submittingComment}
              onClick={submitComment}
            >
              {t('posts.comment', 'Kommentieren')}
            </Button>
          </div>
        )}
      </Paper>
    </div>
  )
}
