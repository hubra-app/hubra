import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Badge, Button, Group, TextInput, Paper, Loader, Center, SegmentedControl } from '@mantine/core'
import {
  IconChecks,
  IconCircleCheck,
  IconClock,
  IconHeart,
  IconMessage2,
} from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useToast, useAuth } from '@/context/AppContext'
import { PageHead, Avatar } from '@/components/ui'
import { DetailBack } from '@/components/detail'
import { formatDateTime } from '@/format'
import { useListCache } from '@/data/lists'
import { PostReadsModal } from './PostReadsModal'
import { MarkdownRenderer } from '@/components/MarkdownRenderer'
import type { ContentLanguage, Post, PostComment as PostCommentType } from '@/types'
import { useLanguageNames } from './contentLanguages'
import { CommentItem } from './CommentItem'
import {
  getPost,
  likePost,
  unlikePost,
  listComments,
  addComment,
  deleteComment,
  postIn,
  postLanguages,
  confirmRead,
} from '@/api/posts'
import { qk } from '@/data/keys'

export function PostDetailScreen() {
  const { id } = useParams<{ id: string }>()
  const { t } = useT()
  const { notify } = useToast()
  const { currentUser, isAdmin, hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const [lang, setLang] = useState<ContentLanguage | null>(null)
  const languageNames = useLanguageNames()

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
  const postCache = useListCache<Post>(qk.posts.all)
  const [readsOpen, setReadsOpen] = useState(false)
  const [confirming, setConfirming] = useState(false)

  const confirm = async () => {
    if (!id) return
    setConfirming(true)
    try {
      const updated = await confirmRead(id)
      queryClient.setQueryData<Post>(qk.posts.one(id), updated)
      postCache.replace(updated)
    } catch (err: unknown) {
      notify('error', t('common.error'), err instanceof Error ? err.message : '')
    } finally {
      setConfirming(false)
    }
  }

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
        <DetailBack to="/app/operations/posts" label={t('shell.nav.posts', 'Beiträge')} />
        <PageHead title={t('posts.notFound', 'Beitrag nicht gefunden')} />
      </div>
    )
  }

  const liked = post.likeMemberIds.includes(currentUser?.id ?? '')

  // The member may read the post in another of its languages.
  const view = lang ? postIn(post, lang) : post
  const languages = postLanguages(post)

  return (
    <div>
      <DetailBack to="/app/operations/posts" label={t('shell.nav.posts', 'Beiträge')} />
      <PageHead title={view.title} desc={view.summary ?? undefined} />
      <Paper withBorder style={{ padding: '24px' }}>
        <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
          <Avatar name={post.author} color={post.avatarColor} size={38} />
          <div>
            <div
              style={{
                fontSize: 'var(--mantine-font-size-sm)',
                fontWeight: 600,
                color: 'var(--hb-text)',
              }}
            >
              {post.author}
            </div>
            <div
              className="num"
              style={{
                fontSize: 'var(--mantine-font-size-xs)',
                color: 'var(--hb-text-3)',
              }}
            >
              {post.time}
            </div>
          </div>
        </div>
        <div
          style={{
            fontSize: 'var(--mantine-font-size-sm)',
            color: 'var(--hb-text)',
            lineHeight: 1.6,
            marginBottom: 16,
          }}
        >
          {languages.length > 1 && (
            <SegmentedControl
              size="xs"
              mb="sm"
              data-testid="post-language-switch"
              value={view.shownLanguage ?? languages[0]}
              onChange={(v) => setLang(v as ContentLanguage)}
              data={languages.map((l) => ({ value: l, label: languageNames[l] }))}
              aria-label={t('content.readIn', 'Sprache')}
            />
          )}
          <MarkdownRenderer content={view.body} />
        </div>
        {post.publishAt && (
          <Badge variant="light" color="violet" mb="md" leftSection={<IconClock size={12} />} style={{ textTransform: 'none' }}>
            {t('posts.schedule.badge', 'Geplant für {{when}}', { when: formatDateTime(post.publishAt) })}
          </Badge>
        )}
        {post.mustRead && (
          <Group gap="xs" mb="md" data-testid="must-read-row">
            {post.readByMe ? (
              <Badge color="green" variant="light" leftSection={<IconCircleCheck size={12} />} style={{ textTransform: 'none' }}>
                {t('posts.mustRead.done', 'Gelesen bestätigt')}
              </Badge>
            ) : (
              !post.publishAt && (
                <Button size="sm" leftSection={<IconCircleCheck size={16} />} loading={confirming} onClick={() => void confirm()} data-testid="confirm-read">
                  {t('posts.mustRead.confirm', 'Gelesen, bestätigen')}
                </Button>
              )
            )}
            {(isAdmin || hasPermission('posts.posts.update') || post.authorId === currentUser?.id) && (
              <Button size="sm" variant="subtle" leftSection={<IconChecks size={16} />} onClick={() => setReadsOpen(true)} data-testid="read-status">
                {t('posts.mustRead.count', '{{count}} bestätigt', { count: post.readCount })}
              </Button>
            )}
          </Group>
        )}
        <div
          style={{
            display: 'flex',
            gap: 12,
            borderTop: '1px solid var(--hb-border)',
            paddingTop: 12,
          }}
        >
          {canLike && (
            <Button
              size="sm"
              variant="subtle"
              style={{ color: liked ? 'var(--mantine-color-red-text)' : 'var(--hb-text-2)' }}
              onClick={toggleLike}
            >
              <IconHeart
                size={16}
                style={{ fill: liked ? 'var(--mantine-color-red-text)' : 'none' }}
              />
              {post.likes}
            </Button>
          )}
          <Button size="sm" variant="subtle" style={{ color: 'var(--hb-text-2)' }}>
            <IconMessage2 size={16} />
            {post.comments}
          </Button>
        </div>
      </Paper>

      <PostReadsModal post={readsOpen ? post : null} onClose={() => setReadsOpen(false)} />
      <Paper
        withBorder
        style={{ marginTop: 16, padding: '24px' }}
      >
        <div
          style={{
            fontSize: 'var(--mantine-font-size-sm)',
            fontWeight: 700,
            color: 'var(--hb-text)',
            marginBottom: 16,
          }}
        >
          {t('posts.comments', 'Kommentare')}
        </div>
        {comments.length === 0 ? (
          <div
            style={{
              fontSize: 'var(--mantine-font-size-xs)',
              color: 'var(--hb-text-3)',
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
              <CommentItem
                key={comment.id}
                postId={id!}
                comment={comment}
                canDelete={
                  (canComment && (comment.authorId === currentUser?.id || canModerate)) || isAdmin
                }
                onDelete={() => removeComment(comment.id)}
                onChange={(updated) =>
                  queryClient.setQueryData<PostCommentType[]>(qk.posts.comments(id), (prev) =>
                    (prev ?? []).map((c) => (c.id === updated.id ? updated : c)),
                  )
                }
              />
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
