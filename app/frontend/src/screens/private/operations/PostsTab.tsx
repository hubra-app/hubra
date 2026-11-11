import { lazy, Suspense, useState, useCallback } from 'react'
import { ActionIcon, Alert, Anchor, Badge, Button, Checkbox, Group, Loader, Menu, SimpleGrid, Text, TextInput, Paper } from '@mantine/core'
import { Link } from 'react-router-dom'
import { DateTimeField, FilterBar } from '@hubra/ui'
import { filterLabels } from '@/components/filterLabels'
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
  IconClock,
  IconEyeOff,
  IconChecks,
  IconCircleCheck,
  IconAlertCircle,
  IconDotsVertical,
  IconNews,
  IconPencil,
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
  EmptyState,
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
  confirmRead,
} from '@/api/posts'
import { PostReadsModal } from './PostReadsModal'
import { GroupBadge, GroupField } from './ContentGroupFields'
import { PostLanguagesField } from './PostLanguagesField'
import { useContentGroups } from './contentGroups'
import { fromLocalInput, toLocalInput } from './localInput'
import { formatDateTime } from '@/format'

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
  // datetime-local values; empty: now / never.
  publishAt: z.string(),
  hideAfter: z.string(),
  mustRead: z.boolean(),
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
  const [readsFor, setReadsFor] = useState<Post | null>(null)
  const [expandedBodies, setExpandedBodies] = useState<Set<string>>(new Set())
  const [expandedComments, setExpandedComments] = useState<Set<string>>(
    new Set(),
  )
  const [commentsCache, setCommentsCache] = useState<
    Record<string, PostComment[]>
  >({})
  const [commentInput, setCommentInput] = useState('')
  const [submittingComment, setSubmittingComment] = useState(false)

  const [search, setSearch] = useState('')
  const [show, setShow] = useState<'all' | 'unread' | 'scheduled'>('all')
  // What still waits for the member's read confirmation, shown on top.
  const unreadMust = (p: Post) => p.mustRead && !p.readByMe && !p.publishAt
  const unreadCount = posts.filter(unreadMust).length
  const scheduledCount = posts.filter((p) => p.publishAt).length
  const shown = posts
    .filter((p) => {
      const q = search.trim().toLowerCase()
      const matchSearch =
        !q || p.title.toLowerCase().includes(q) || p.body.toLowerCase().includes(q) || p.author.toLowerCase().includes(q)
      const matchShow = show === 'all' || (show === 'unread' ? unreadMust(p) : !!p.publishAt)
      return matchSearch && matchShow
    })
    // Unconfirmed must-read posts first; otherwise the order the API gives (newest first).
    .sort((a, b) => Number(unreadMust(b)) - Number(unreadMust(a)))
  const pg = usePagination(shown, 10)

  const form = useForm<PostForm>({
    validate: zod4Resolver(postSchema),
    initialValues: { title: '', summary: '', body: '', groupId: '', language: readerLanguage(), translations: {}, publishAt: '', hideAfter: '', mustRead: false },
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
      publishAt: '',
      hideAfter: '',
      mustRead: false,
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
      publishAt: toLocalInput(post.publishAt),
      hideAfter: toLocalInput(post.hideAfter),
      mustRead: post.mustRead,
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
        publishAt: fromLocalInput(data.publishAt),
        hideAfter: fromLocalInput(data.hideAfter),
        mustRead: data.mustRead,
      })
      postCache.prepend(post)
      setAddOpen(false)
      if (post.publishAt)
        notify(
          'success',
          t('posts.schedule.scheduled', 'Beitrag geplant'),
          t('posts.schedule.scheduledMsg', 'Er erscheint am {{when}}. Bis dahin siehst nur du ihn (und wer ihn bearbeiten darf).', {
            when: formatDateTime(post.publishAt),
          }),
        )
      else
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
        // Only what changed: a post that is out cannot be scheduled again,
        // and an expired one keeps its past date until it gets a new one.
        ...(editTarget.publishAt && data.publishAt !== toLocalInput(editTarget.publishAt)
          ? { publishAt: fromLocalInput(data.publishAt) }
          : {}),
        ...(data.hideAfter !== toLocalInput(editTarget.hideAfter)
          ? { hideAfter: fromLocalInput(data.hideAfter) }
          : {}),
        mustRead: data.mustRead,
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

  const readMutation = useMutation({
    mutationFn: (postId: string) => confirmRead(postId),
    onSuccess: (post) => postCache.replace(post),
    onError: (err) =>
      notify(
        'error',
        t('common.error'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      ),
  })

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
      {/* A post that is out cannot be scheduled again. */}
      <SimpleGrid cols={{ base: 1, sm: !editTarget || editTarget.publishAt ? 2 : 1 }}>
        {(!editTarget || editTarget.publishAt) && (
          <Field
            label={t('posts.schedule.publishAt', 'Veröffentlichen am (optional)')}
            hint={t('posts.schedule.publishAtHint', 'Leer: sofort. Die Mitglieder werden dann benachrichtigt.')}
          >
            <DateTimeField data-testid="post-publish-at" {...form.getInputProps('publishAt')} />
          </Field>
        )}
        <Field
          label={t('posts.schedule.hideAfter', 'Ausblenden nach (optional)')}
          hint={t('posts.schedule.hideAfterHint', 'Danach sehen ihn die Mitglieder nicht mehr, z. B. eine Platzsperre.')}
        >
          <DateTimeField data-testid="post-hide-after" {...form.getInputProps('hideAfter')} />
        </Field>
      </SimpleGrid>
      <Checkbox
        label={t('posts.mustRead.field', 'Lesebestätigung verlangen')}
        description={t(
          'posts.mustRead.fieldHint',
          'Für Sicherheitsregeln, Regeländerungen oder GV-Unterlagen: Mitglieder bestätigen mit einem Tipp, du siehst, wer noch fehlt.',
        )}
        {...form.getInputProps('mustRead', { type: 'checkbox' })}
        data-testid="post-must-read"
      />
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
      {unreadCount > 0 && show !== 'unread' && (
        <Alert
          variant="light"
          color="orange"
          mb="md"
          icon={<IconAlertCircle size={18} />}
          data-testid="must-read-banner"
        >
          <Group justify="space-between" gap="xs">
            <Text size="sm">
              {t('posts.mustRead.banner', '{{count}} Pflicht-Beitrag wartet auf deine Lesebestätigung.', {
                count: unreadCount,
              })}
            </Text>
            <Button size="xs" variant="light" color="orange" onClick={() => setShow('unread')}>
              {t('posts.mustRead.showUnread', 'Anzeigen')}
            </Button>
          </Group>
        </Alert>
      )}
      <Paper withBorder>
        <FilterBar
          padded
          search={search}
          onSearchChange={setSearch}
          searchPlaceholder={t('posts.search', 'Beiträge durchsuchen …')}
          labels={filterLabels()}
          groups={[
            {
              key: 'show',
              label: t('posts.filter.show', 'Anzeigen'),
              value: show,
              defaultValue: 'all',
              options: [
                { value: 'all', label: t('common.all', 'Alle') },
                { value: 'unread', label: t('posts.filter.unread', 'Noch nicht bestätigt') },
                ...(canCreate || scheduledCount > 0
                  ? [{ value: 'scheduled', label: t('posts.filter.scheduled', 'Geplant') }]
                  : []),
              ],
              onChange: (v) => setShow(v as 'all' | 'unread' | 'scheduled'),
            },
          ]}
        />
        {pg.total > pg.perPage && <Pagination {...pg} top />}
        {pg.paged.length === 0 && (search || show !== 'all') ? (
          <EmptyState
            icon={<IconNews size={36} />}
            title={
              show === 'unread'
                ? t('posts.filter.noneUnread', 'Alles gelesen und bestätigt.')
                : t('posts.noMatch', 'Keine Beiträge gefunden.')
            }
          />
        ) : pg.paged.length === 0 ? (
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
                className="hb-post-card"
                data-testid="post-card"
                data-unread={unreadMust(post) || undefined}
              >
                <div className="hb-post-head">
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <Group gap={8} wrap="wrap" mb={4}>
                      <Anchor
                        component={Link}
                        to={`/app/operations/posts/${post.id}`}
                        c="var(--hb-text)"
                        fw={700}
                        fz="lg"
                        underline="hover"
                        data-testid="post-title"
                      >
                        {post.title}
                      </Anchor>
                      {post.mustRead && (
                        <Badge
                          variant="light"
                          color={post.readByMe ? 'green' : 'orange'}
                          size="sm"
                          style={{ textTransform: 'none' }}
                        >
                          {post.readByMe
                            ? t('posts.mustRead.done', 'Gelesen bestätigt')
                            : t('posts.mustRead.badge', 'Pflicht')}
                        </Badge>
                      )}
                      {post.publishAt && (
                        <Badge variant="light" color="violet" size="sm" leftSection={<IconClock size={12} />} style={{ textTransform: 'none' }}>
                          {t('posts.schedule.badge', 'Geplant für {{when}}', { when: formatDateTime(post.publishAt) })}
                        </Badge>
                      )}
                      {!post.publishAt && post.hideAfter && new Date(post.hideAfter) <= new Date() && (
                        <Badge variant="light" color="gray" size="sm" leftSection={<IconEyeOff size={12} />} style={{ textTransform: 'none' }}>
                          {t('posts.schedule.hidden', 'Ausgeblendet')}
                        </Badge>
                      )}
                    </Group>
                    <div className="hb-post-byline">
                      <Avatar name={post.author} color={post.avatarColor} size={22} />
                      <span style={{ fontWeight: 600, color: 'var(--hb-text-2)' }}>{post.author}</span>
                      <span>·</span>
                      <span>{post.time}</span>
                      <GroupBadge name={createScope.groupName(post.groupId)} />
                    </div>
                  </div>
                  {(canEditPost(post) || canDeletePost(post)) && (
                    <Menu position="bottom-end" withinPortal>
                      <Menu.Target>
                        <ActionIcon
                          variant="subtle"
                          color="gray"
                          size="lg"
                          aria-label={t('common.moreActions', 'Weitere Aktionen')}
                          data-testid="post-menu"
                        >
                          <IconDotsVertical size={18} />
                        </ActionIcon>
                      </Menu.Target>
                      <Menu.Dropdown>
                        {canEditPost(post) && (
                          <Menu.Item leftSection={<IconPencil size={16} />} onClick={() => openEdit(post)}>
                            {t('common.edit', 'Bearbeiten')}
                          </Menu.Item>
                        )}
                        {canEditPost(post) && post.mustRead && (
                          <Menu.Item leftSection={<IconChecks size={16} />} onClick={() => setReadsFor(post)}>
                            {t('posts.mustRead.who', 'Wer hat bestätigt?')}
                          </Menu.Item>
                        )}
                        {canDeletePost(post) && (
                          <>
                            {canEditPost(post) && <Menu.Divider />}
                            <Menu.Item color="red" leftSection={<IconTrash size={16} />} onClick={() => setDeleteTarget(post)}>
                              {t('common.delete', 'Löschen')}
                            </Menu.Item>
                          </>
                        )}
                      </Menu.Dropdown>
                    </Menu>
                  )}
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
                {post.mustRead && (
                  <Group gap="xs" mb={14} data-testid="must-read-row">
                    {post.readByMe ? (
                      <Badge color="green" variant="light" leftSection={<IconCircleCheck size={12} />} style={{ textTransform: 'none' }}>
                        {t('posts.mustRead.done', 'Gelesen bestätigt')}
                      </Badge>
                    ) : (
                      !post.publishAt && (
                        <Button
                          size="xs"
                          leftSection={<IconCircleCheck size={14} />}
                          loading={readMutation.isPending && readMutation.variables === post.id}
                          onClick={() => readMutation.mutate(post.id)}
                          data-testid="confirm-read"
                        >
                          {t('posts.mustRead.confirm', 'Gelesen, bestätigen')}
                        </Button>
                      )
                    )}
                    {canEditPost(post) && (
                      <Button
                        size="xs"
                        variant="subtle"
                        leftSection={<IconChecks size={14} />}
                        onClick={() => setReadsFor(post)}
                        data-testid="read-status"
                      >
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
              {form.values.publishAt && new Date(form.values.publishAt) > new Date()
                ? t('posts.schedule.submit', 'Planen')
                : t('posts.publish', 'Veröffentlichen')}
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
      <PostReadsModal post={readsFor} onClose={() => setReadsFor(null)} />
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
