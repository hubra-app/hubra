import { useState, useCallback } from 'react'
import { Button, Group, TextInput, Paper } from '@mantine/core'
import { useForm } from '@mantine/form'
import { zodResolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { useMutation } from '@tanstack/react-query'
import { useT } from '@/locales/i18n'
import {
  IconPlus,
  IconTrash,
  IconHeart,
  IconMessage2,
  IconArrowBackUp,
} from '@tabler/icons-react'
import { useToast, useAuth, useData } from '@/context/AppContext'
import {
  Modal,
  Field,
  Avatar,
  usePagination,
  Pagination,
  ConfirmModal,
  ActionButtons,
} from '@/components/ui'
import { RichTextEditor } from '@/components/RichTextEditor'
import { MarkdownRenderer } from '@/components/MarkdownRenderer'
import type { Post, PostComment } from '@/types'
import {
  createPost,
  updatePost,
  deletePost,
  getPost,
  likePost,
  unlikePost,
  listComments,
  addComment,
  deleteComment,
} from '@/api/posts'

const postSchema = z.object({
  title: z.string().min(1, 'Title is required'),
  summary: z.string(),
  body: z.string().refine((v) => v.trim().length > 0, 'Content is required'),
})
type PostForm = z.infer<typeof postSchema>

/* -- Posts ------------------------------------ */
export function PostsTab() {
  const { notify } = useToast()
  const { currentUser, hasPermission, isAdmin } = useAuth()
  const { posts, setPosts } = useData()
  const { t } = useT()
  const canCreate = hasPermission('posts.posts.create')
  const canUpdate = hasPermission('posts.posts.update')
  const canDelete = hasPermission('posts.posts.delete')
  const canLike = hasPermission('posts.posts.like')
  const canComment = hasPermission('posts.posts.comment')

  const [addOpen, setAddOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<Post | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Post | null>(null)
  const [expandedBodies, setExpandedBodies] = useState<Set<string>>(new Set())
  const [expandedComments, setExpandedComments] = useState<Set<string>>(
    new Set(),
  )
  const [commentsCache, setCommentsCache] = useState<
    Record<string, PostComment[]>
  >({})
  const [commentInput, setCommentInput] = useState('')
  const [submittingComment, setSubmittingComment] = useState(false)

  const pg = usePagination(posts, 10)

  const form = useForm<PostForm>({
    validate: zodResolver(postSchema),
    initialValues: { title: '', summary: '', body: '' },
  })

  const openAdd = () => {
    form.setValues({ title: '', summary: '', body: '' })
    setAddOpen(true)
  }
  const openEdit = (post: Post) => {
    setEditTarget(post)
    form.setValues({
      title: post.title,
      summary: post.summary ?? '',
      body: post.body,
    })
  }

  const saveAdd = async (data: PostForm) => {
    try {
      const post = await createPost({
        title: data.title,
        summary: data.summary || undefined,
        body: data.body,
      })
      setPosts((prev) => [post, ...prev])
      setAddOpen(false)
      notify(
        'success',
        t('posts.post.published', 'Post published'),
        t(
          'posts.post.publishedMsg',
          'Your post is now visible to all members.',
        ),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unknown error'),
      )
    }
  }

  const saveEdit = async (data: PostForm) => {
    if (!editTarget) return
    try {
      const post = await updatePost(editTarget.id, {
        title: data.title,
        summary: data.summary || undefined,
        body: data.body,
      })
      setPosts((prev) => prev.map((p) => (p.id === post.id ? post : p)))
      setEditTarget(null)
      notify(
        'success',
        t('posts.post.updated', 'Post updated'),
        t('posts.post.updatedMsg', 'Changes saved.'),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unknown error'),
      )
    }
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    try {
      await deletePost(deleteTarget.id)
      setPosts((prev) => prev.filter((p) => p.id !== deleteTarget.id))
      notify(
        'info',
        t('posts.post.deleted', 'Post deleted'),
        t('posts.post.deletedMsg', { title: deleteTarget.title }),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unknown error'),
      )
    }
  }

  const likeMutation = useMutation({
    mutationFn: ({ postId, liked }: { postId: string; liked: boolean }) =>
      liked ? unlikePost(postId) : likePost(postId),
    onMutate: ({ postId, liked }) => {
      const myId = currentUser?.id ?? ''
      setPosts((prev) =>
        prev.map((p) => {
          if (p.id !== postId) return p
          const likeMemberIds = liked
            ? p.likeMemberIds.filter((id) => id !== myId)
            : p.likeMemberIds.includes(myId)
              ? p.likeMemberIds
              : [...p.likeMemberIds, myId]
          return {
            ...p,
            likeMemberIds,
            likes: likeMemberIds.length,
          }
        }),
      )
      return { liked }
    },
    onError: (err, { postId }) => {
      const msg = err instanceof Error ? err.message : 'Could not toggle like.'
      notify('error', t('common.error'), msg)
      getPost(postId).then((post) => {
        setPosts((prev) => prev.map((p) => (p.id === post.id ? post : p)))
      })
    },
    onSuccess: (post) => {
      setPosts((prev) => prev.map((p) => (p.id === post.id ? post : p)))
    },
  })

  const toggleLike = (post: Post) => {
    const liked = post.likeMemberIds.includes(currentUser?.id ?? '')
    likeMutation.mutate({ postId: post.id, liked })
  }

  const toggleExpandBody = (postId: string) => {
    setExpandedBodies((prev) => {
      const next = new Set(prev)
      if (next.has(postId)) next.delete(postId)
      else next.add(postId)
      return next
    })
  }

  const toggleComments = useCallback(
    async (postId: string) => {
      setExpandedComments((prev) => {
        const next = new Set(prev)
        if (next.has(postId)) next.delete(postId)
        else next.add(postId)
        return next
      })
      if (!commentsCache[postId]) {
        try {
          const comments = await listComments(postId)
          setCommentsCache((prev) => ({ ...prev, [postId]: comments }))
        } catch {
          // ignore — empty list shown
        }
      }
    },
    [commentsCache],
  )

  const submitComment = async (postId: string) => {
    if (!commentInput.trim()) return
    setSubmittingComment(true)
    try {
      const comment = await addComment(postId, commentInput.trim())
      setCommentsCache((prev) => ({
        ...prev,
        [postId]: [...(prev[postId] ?? []), comment],
      }))
      setPosts((prev) =>
        prev.map((p) =>
          p.id === postId ? { ...p, comments: p.comments + 1 } : p,
        ),
      )
      setCommentInput('')
      notify('success', t('posts.commentAdded', 'Comment added'), '')
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unknown error'),
      )
    } finally {
      setSubmittingComment(false)
    }
  }

  const removeComment = async (postId: string, commentId: string) => {
    try {
      await deleteComment(postId, commentId)
      setCommentsCache((prev) => ({
        ...prev,
        [postId]: (prev[postId] ?? []).filter((c) => c.id !== commentId),
      }))
      setPosts((prev) =>
        prev.map((p) =>
          p.id === postId ? { ...p, comments: p.comments - 1 } : p,
        ),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unknown error'),
      )
    }
  }

  const postForm = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Field label={t('posts.titleLabel', 'Title')}>
        <TextInput
          {...form.getInputProps('title')}
          placeholder={t(
            'posts.titlePlaceholder',
            'New dust extractor installed!',
          )}
        />
      </Field>
      <Field label={t('posts.summaryLabel', 'Summary (optional)')}>
        <TextInput
          {...form.getInputProps('summary')}
          placeholder={t(
            'posts.summaryPlaceholder',
            'A short teaser shown in the list',
          )}
        />
      </Field>
      <Field label={t('posts.content.label', 'Content')}>
        <RichTextEditor
          value={form.values.body}
          onChange={(val) => form.setFieldValue('body', val)}
          placeholder={t(
            'posts.content.placeholder',
            'Share an update with the club…',
          )}
        />
      </Field>
    </div>
  )

  const canEditPost = (post: Post) =>
    (canUpdate && post.authorId === currentUser?.id) || isAdmin

  const canDeletePost = (post: Post) =>
    (canDelete && post.authorId === currentUser?.id) || isAdmin

  return (
    <div>
      {canCreate && (
        <Group justify="flex-end" mb={16}>
          <Button variant="filled" onClick={openAdd}>
            <IconPlus size={16} />
            {t('posts.newPost', 'New Post')}
          </Button>
        </Group>
      )}
      <Paper withBorder shadow="sm" radius="lg">
        <Pagination {...pg} top />
        {pg.paged.length === 0 ? (
          <div
            style={{ padding: '48px', textAlign: 'center', color: '#8c86a0' }}
          >
            <div style={{ fontSize: 32, marginBottom: 12 }}>📢</div>
            <div
              style={{
                fontSize: 'var(--mantine-font-size-sm)',
                fontWeight: 500,
              }}
            >
              {t('posts.noPostsYet', 'No posts yet')}
            </div>
            <div
              style={{ fontSize: 'var(--mantine-font-size-sm)', marginTop: 4 }}
            >
              {t(
                'posts.beFirstToShare',
                'Be the first to share an update with the club.',
              )}
            </div>
          </div>
        ) : (
          pg.paged.map((post) => {
            const liked = post.likeMemberIds.includes(currentUser?.id ?? '')
            const bodyExpanded = expandedBodies.has(post.id)
            const commentsExpanded = expandedComments.has(post.id)
            const comments = commentsCache[post.id] ?? []
            return (
              <div
                key={post.id}
                style={{
                  padding: '20px 24px',
                  borderBottom: '1px solid #e6e3ef',
                }}
              >
                <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
                  <Avatar
                    name={post.author}
                    color={post.avatarColor}
                    size={38}
                  />
                  <div style={{ flex: 1 }}>
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
                  <div style={{ display: 'flex', gap: 6 }}>
                    <ActionButtons
                      onEdit={
                        canEditPost(post) ? () => openEdit(post) : undefined
                      }
                      onDelete={
                        canDeletePost(post)
                          ? () => setDeleteTarget(post)
                          : undefined
                      }
                    />
                  </div>
                </div>
                <div
                  style={{
                    fontSize: 'var(--mantine-font-size-md)',
                    fontWeight: 700,
                    color: '#1a1625',
                    marginBottom: 8,
                  }}
                >
                  {post.title}
                </div>
                <div
                  style={{
                    fontSize: 'var(--mantine-font-size-sm)',
                    color: '#2e2940',
                    lineHeight: 1.6,
                    margin: '0 0 14px',
                  }}
                >
                  {bodyExpanded ? (
                    <MarkdownRenderer content={post.body} />
                  ) : (
                    post.snippet
                  )}
                  {!bodyExpanded && post.body.length > post.snippet.length && (
                    <Button
                      variant="subtle"
                      size="compact-sm"
                      onClick={() => toggleExpandBody(post.id)}
                      style={{ marginLeft: 4, padding: '0 4px' }}
                    >
                      {t('posts.readMore', 'Read more')}
                    </Button>
                  )}
                  {bodyExpanded && (
                    <Button
                      variant="subtle"
                      size="compact-sm"
                      onClick={() => toggleExpandBody(post.id)}
                      style={{ marginLeft: 4, padding: '0 4px' }}
                    >
                      <IconArrowBackUp size={14} />
                      {t('posts.showLess', 'Show less')}
                    </Button>
                  )}
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
                      style={{
                        color: liked ? '#ff4d3d' : '#5e5873',
                      }}
                      onClick={() => toggleLike(post)}
                    >
                      <IconHeart
                        size={16}
                        style={{
                          fill: liked ? '#ff4d3d' : 'none',
                        }}
                      />
                      {post.likes}
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="subtle"
                    style={{ color: '#5e5873' }}
                    onClick={() => toggleComments(post.id)}
                  >
                    <IconMessage2 size={16} />
                    {post.comments}
                  </Button>
                </div>

                {commentsExpanded && (
                  <div
                    style={{
                      marginTop: 12,
                      paddingTop: 12,
                      borderTop: '1px solid #e6e3ef',
                    }}
                  >
                    {comments.length === 0 ? (
                      <div
                        style={{
                          fontSize: 'var(--mantine-font-size-xs)',
                          color: '#8c86a0',
                          marginBottom: 8,
                        }}
                      >
                        {t('posts.noComments', 'No comments yet.')}
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
                          <div
                            key={comment.id}
                            style={{ display: 'flex', gap: 8 }}
                          >
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
                                  comment.authorId === currentUser?.id) ||
                                  isAdmin) && (
                                  <Button
                                    size="compact-xs"
                                    variant="subtle"
                                    style={{
                                      color: '#ff4d3d',
                                      marginLeft: 'auto',
                                    }}
                                    onClick={() =>
                                      removeComment(post.id, comment.id)
                                    }
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
                          placeholder={t(
                            'posts.commentPlaceholder',
                            'Write a comment…',
                          )}
                          style={{ flex: 1 }}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                              e.preventDefault()
                              submitComment(post.id)
                            }
                          }}
                        />
                        <Button
                          variant="filled"
                          size="sm"
                          disabled={!commentInput.trim() || submittingComment}
                          onClick={() => submitComment(post.id)}
                        >
                          {t('posts.comment', 'Comment')}
                        </Button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })
        )}
        <Pagination {...pg} />
      </Paper>

      <Modal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title={t('posts.newPost', 'New Post')}
        footer={
          <>
            <Button variant="default" onClick={() => setAddOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button variant="filled" onClick={() => form.onSubmit(saveAdd)()}>
              {t('posts.publish', 'Publish')}
            </Button>
          </>
        }
      >
        {postForm}
      </Modal>
      <Modal
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        title={t('posts.editPost', 'Edit Post')}
        subtitle={editTarget?.title}
        footer={
          <>
            <Button variant="default" onClick={() => setEditTarget(null)}>
              {t('common.cancel')}
            </Button>
            <Button variant="filled" onClick={() => form.onSubmit(saveEdit)()}>
              {t('common.save')}
            </Button>
          </>
        }
      >
        {postForm}
      </Modal>
      <ConfirmModal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title={t('posts.deletePostTitle', 'Delete post?')}
        body={t(
          'posts.deletePostBody',
          'This post will be permanently removed.',
        )}
        onConfirm={confirmDelete}
      />
    </div>
  )
}
