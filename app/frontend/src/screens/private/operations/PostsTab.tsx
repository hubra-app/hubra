import { lazy, Suspense, useState, useCallback } from 'react'
import { Button, Group, Loader, TextInput, Paper } from '@mantine/core'
import { useForm } from '@mantine/form'
import { zod4Resolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { useMutation } from '@tanstack/react-query'
import { useT, zmsg } from '@/locales/i18n'
import {
  IconPlus,
  IconTrash,
  IconHeart,
  IconMessage2,
  IconArrowBackUp,
} from '@tabler/icons-react'
import { useToast, useAuth } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { useListCache, usePosts } from '@/data/lists'
import {
  Modal,
  Field,
  Avatar,
  usePagination,
  Pagination,
  ConfirmModal,
  ActionButtons,
  useSubmitOnce,
} from '@/components/ui'
import { MarkdownRenderer } from '@/components/MarkdownRenderer'
import type { ContentLanguage, Post, PostComment } from '@/types'
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
  readerLanguage,
} from '@/api/posts'
import { GroupBadge, GroupField } from './ContentGroupFields'
import { PostLanguagesField } from './PostLanguagesField'
import { useContentGroups } from './contentGroups'

// The editor is large and only needed while writing a post.
const RichTextEditor = lazy(() =>
  import('@/components/RichTextEditor').then((m) => ({ default: m.RichTextEditor })),
)

const postSchema = z.object({
  title: z.string().min(1, zmsg('validation.titleRequired', 'Titel ist erforderlich')),
  summary: z.string(),
  body: z.string().refine((v) => v.trim().length > 0, zmsg('validation.contentRequired', 'Inhalt ist erforderlich')),
  groupId: z.string(),
  language: z.enum(['de', 'fr', 'it', 'en']),
  translations: z.record(z.string(), z.object({ title: z.string(), summary: z.string().nullable(), body: z.string() })),
})
type PostForm = z.infer<typeof postSchema>

/** Translations worth sending: a language with a title and a text. */
function filledTranslations(form: PostForm): Post['translations'] {
  const out: Post['translations'] = {}
  for (const [lang, text] of Object.entries(form.translations)) {
    if (lang !== form.language && (text.title.trim() || text.body.trim()))
      out[lang as ContentLanguage] = text
  }
  return out
}

/* -- Posts ------------------------------------ */
export function PostsTab() {
  const { notify } = useToast()
  const { currentUser, hasPermission, hasGroupPermission, isAdmin } = useAuth()
  const { posts } = usePosts()
  const postCache = useListCache<Post>(qk.posts.all)
  const { t } = useT()
  // Club-wide, or through a role for one group (that group's posts).
  const createScope = useContentGroups('posts.posts.create')
  const updateScope = useContentGroups('posts.posts.update')
  const canCreate = createScope.canAny
  const canUpdate = hasPermission('posts.posts.update')
  const canDelete = hasPermission('posts.posts.delete')
  const canLike = hasPermission('posts.posts.like')
  const canComment = hasPermission('posts.posts.comment')
  // Moderators edit and remove other members' posts and comments too.
  const canModerate = hasPermission('posts.posts.moderate')

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
    validate: zod4Resolver(postSchema),
    initialValues: { title: '', summary: '', body: '', groupId: '', language: readerLanguage(), translations: {} },
  })
  const formScope = editTarget ? updateScope : createScope

  const openAdd = () => {
    form.setValues({
      title: '',
      summary: '',
      body: '',
      groupId: createScope.defaultGroup,
      language: readerLanguage(),
      translations: {},
    })
    setAddOpen(true)
  }
  const openEdit = (post: Post) => {
    setEditTarget(post)
    // The editor works on the post as written, not the member's language.
    form.setValues({
      title: post.original.title,
      summary: post.original.summary ?? '',
      body: post.original.body,
      groupId: post.groupId ?? '',
      language: post.language ?? readerLanguage(),
      translations: post.translations as PostForm['translations'],
    })
  }

  const saveAdd = async (data: PostForm) => {
    try {
      const post = await createPost({
        title: data.title,
        summary: data.summary || undefined,
        body: data.body,
        groupId: data.groupId || null,
        language: data.language,
        translations: filledTranslations(data),
      })
      postCache.prepend(post)
      setAddOpen(false)
      notify(
        'success',
        t('posts.post.published', 'Beitrag veröffentlicht'),
        t(
          'posts.post.publishedMsg',
          'Dein Beitrag ist jetzt für alle Mitglieder sichtbar.',
        ),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }
  const [submitAdd, adding] = useSubmitOnce(saveAdd)

  const saveEdit = async (data: PostForm) => {
    if (!editTarget) return
    try {
      const post = await updatePost(editTarget.id, {
        title: data.title,
        summary: data.summary || undefined,
        body: data.body,
        groupId: data.groupId || null,
        language: data.language,
        translations: filledTranslations(data),
      })
      postCache.replace(post)
      setEditTarget(null)
      notify(
        'success',
        t('posts.post.updated', 'Beitrag gespeichert'),
        t('posts.post.updatedMsg', 'Änderungen gespeichert.'),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    try {
      await deletePost(deleteTarget.id)
      postCache.remove(deleteTarget.id)
      notify(
        'info',
        t('posts.post.deleted', 'Beitrag gelöscht'),
        t('posts.post.deletedMsg', { title: deleteTarget.title }),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }

  const likeMutation = useMutation({
    mutationFn: ({ postId, liked }: { postId: string; liked: boolean }) =>
      liked ? unlikePost(postId) : likePost(postId),
    onMutate: ({ postId, liked }) => {
      const myId = currentUser?.id ?? ''
      postCache.patch(postId, (p) => {
        const likeMemberIds = liked
          ? p.likeMemberIds.filter((id) => id !== myId)
          : p.likeMemberIds.includes(myId)
            ? p.likeMemberIds
            : [...p.likeMemberIds, myId]
        return { ...p, likeMemberIds, likes: likeMemberIds.length }
      })
      return { liked }
    },
    onError: (err, { postId }) => {
      const msg = err instanceof Error ? err.message : t('posts.likeFailed', 'Das Like konnte nicht gespeichert werden.')
      notify('error', t('common.error'), msg)
      getPost(postId).then((post) => {
        postCache.replace(post)
      })
    },
    onSuccess: (post) => {
      postCache.replace(post)
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
      postCache.patch(postId, (p) => ({ ...p, comments: p.comments + 1 }))
      setCommentInput('')
      notify('success', t('posts.commentAdded', 'Kommentar hinzugefügt'), '')
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekannter Fehler'),
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
      postCache.patch(postId, (p) => ({ ...p, comments: p.comments - 1 }))
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }

  const postForm = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Field label={t('posts.titleLabel', 'Titel')}>
        <TextInput
          {...form.getInputProps('title')}
          placeholder={t(
            'posts.titlePlaceholder',
            'Neue Absauganlage installiert!',
          )}
        />
      </Field>
      <Field label={t('posts.summaryLabel', 'Zusammenfassung (optional)')}>
        <TextInput
          {...form.getInputProps('summary')}
          placeholder={t(
            'posts.summaryPlaceholder',
            'Ein kurzer Anriss für die Liste',
          )}
        />
      </Field>
      <GroupField
        scope={formScope}
        value={form.values.groupId}
        onChange={(v) => form.setFieldValue('groupId', v)}
        hint={t(
          'content.groupHint',
          'Wer eine Rolle für diese Gruppe hat, kann den Eintrag verwalten. Sichtbar bleibt er für alle.',
        )}
      />
      <Field label={t('posts.content.label', 'Inhalt')}>
        <Suspense fallback={<Loader size="sm" />}>
          <RichTextEditor
            value={form.values.body}
            onChange={(val) => form.setFieldValue('body', val)}
            placeholder={t(
              'posts.content.placeholder',
              'Teile eine Neuigkeit mit dem Verein …',
            )}
          />
        </Suspense>
      </Field>
      <PostLanguagesField
        language={form.values.language}
        translations={form.values.translations as Post['translations']}
        original={{ title: form.values.title, summary: form.values.summary || null, body: form.values.body }}
        onLanguage={(v) => form.setFieldValue('language', v)}
        onTranslations={(v) => form.setFieldValue('translations', v as PostForm['translations'])}
        renderBody={(value, onChange) => (
          <Field label={t('posts.content.label', 'Inhalt')}>
            <Suspense fallback={<Loader size="sm" />}>
              <RichTextEditor value={value} onChange={onChange} />
            </Suspense>
          </Field>
        )}
      />
    </div>
  )

  // A role for the post's group manages it like a moderator (the API checks
  // the same).
  const inGroup = (post: Post, key: string) =>
    hasGroupPermission(key, post.groupId) ||
    hasGroupPermission('posts.posts.moderate', post.groupId)
  const mayManage = (post: Post, key: string, clubWide: boolean) =>
    isAdmin ||
    ((clubWide || hasGroupPermission(key, post.groupId)) &&
      (post.authorId === currentUser?.id || canModerate || inGroup(post, key)))
  const canEditPost = (post: Post) => mayManage(post, 'posts.posts.update', canUpdate)
  const canDeletePost = (post: Post) => mayManage(post, 'posts.posts.delete', canDelete)

  return (
    <div>
      {canCreate && (
        <Group justify="flex-end" mb={16} className="page-actions">
          <Button variant="filled" onClick={openAdd}>
            <IconPlus size={16} />
            {t('posts.newPost', 'Neuer Beitrag')}
          </Button>
        </Group>
      )}
      <Paper withBorder>
        <Pagination {...pg} top />
        {pg.paged.length === 0 ? (
          <div
            style={{ padding: '48px', textAlign: 'center', color: 'var(--hb-text-3)' }}
          >
            <div style={{ fontSize: 32, marginBottom: 12 }}>📢</div>
            <div
              style={{
                fontSize: 'var(--mantine-font-size-sm)',
                fontWeight: 500,
              }}
            >
              {t('posts.noPostsYet', 'Noch keine Beiträge')}
            </div>
            <div
              style={{ fontSize: 'var(--mantine-font-size-sm)', marginTop: 4 }}
            >
              {t(
                'posts.beFirstToShare',
                'Teile die erste Neuigkeit mit dem Verein.',
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
                  borderBottom: '1px solid var(--hb-border)',
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
                        color: 'var(--hb-text)',
                      }}
                    >
                      {post.author}
                    </div>
                    <div
                      style={{
                        fontSize: 'var(--mantine-font-size-xs)',
                        color: 'var(--hb-text-3)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        flexWrap: 'wrap',
                      }}
                    >
                      <span className="num">{post.time}</span>
                      <GroupBadge name={createScope.groupName(post.groupId)} />
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
                    color: 'var(--hb-text)',
                    marginBottom: 8,
                  }}
                >
                  {post.title}
                </div>
                <div
                  style={{
                    fontSize: 'var(--mantine-font-size-sm)',
                    color: 'var(--hb-text)',
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
                      {t('posts.readMore', 'Weiterlesen')}
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
                      {t('posts.showLess', 'Weniger anzeigen')}
                    </Button>
                  )}
                </div>
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
                      style={{
                        color: liked ? 'var(--mantine-color-red-text)' : 'var(--hb-text-2)',
                      }}
                      onClick={() => toggleLike(post)}
                    >
                      <IconHeart
                        size={16}
                        style={{
                          fill: liked ? 'var(--mantine-color-red-text)' : 'none',
                        }}
                      />
                      {post.likes}
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="subtle"
                    style={{ color: 'var(--hb-text-2)' }}
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
                      borderTop: '1px solid var(--hb-border)',
                    }}
                  >
                    {comments.length === 0 ? (
                      <div
                        style={{
                          fontSize: 'var(--mantine-font-size-xs)',
                          color: 'var(--hb-text-3)',
                          marginBottom: 8,
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
                                    color: 'var(--hb-text)',
                                  }}
                                >
                                  {comment.author}
                                </span>
                                <span
                                  className="num"
                                  style={{
                                    fontSize: 'var(--mantine-font-size-xs)',
                                    color: 'var(--hb-text-3)',
                                  }}
                                >
                                  {comment.time}
                                </span>
                                {((canComment &&
                                  (comment.authorId === currentUser?.id ||
                                    canModerate)) ||
                                  isAdmin) && (
                                  <Button
                                    size="compact-xs"
                                    variant="subtle"
                                    style={{
                                      color: 'var(--mantine-color-red-text)',
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
                                  color: 'var(--hb-text)',
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
                            'Schreibe einen Kommentar …',
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
                          {t('posts.comment', 'Kommentieren')}
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
        onSubmit={form.onSubmit(submitAdd)}
        open={addOpen}
        onClose={() => setAddOpen(false)}
        wide
        title={t('posts.newPost', 'Neuer Beitrag')}
        footer={
          <>
            <Button variant="default" onClick={() => setAddOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button variant="filled" type="submit" loading={adding}>
              {t('posts.publish', 'Veröffentlichen')}
            </Button>
          </>
        }
      >
        {postForm}
      </Modal>
      <Modal
        onSubmit={form.onSubmit(saveEdit)}
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        wide
        title={t('posts.editPost', 'Beitrag bearbeiten')}
        subtitle={editTarget?.title}
        footer={
          <>
            <Button variant="default" onClick={() => setEditTarget(null)}>
              {t('common.cancel')}
            </Button>
            <Button variant="filled" type="submit">
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
        title={t('posts.deletePostTitle', 'Beitrag löschen?')}
        body={t(
          'posts.deletePostBody',
          'Der Beitrag wird endgültig gelöscht.',
        )}
        onConfirm={confirmDelete}
      />
    </div>
  )
}
