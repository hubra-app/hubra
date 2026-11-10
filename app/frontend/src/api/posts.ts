import { apiFetch } from '@hubra/api-client';
import { formatRelative } from "@/format";
import i18n from "@/locales/i18n";
import type { ContentLanguage, Post, PostComment, PostText } from "@/types";

interface BackendPost {
  id: number;
  author_id: number;
  author_name: string | null;
  author_avatar_color: string | null;
  title: string;
  summary: string | null;
  body: string;
  created_at: string;
  updated_at: string;
  like_count: number;
  like_member_ids: number[];
  comment_count: number;
  group_id?: number | null;
  language?: ContentLanguage | null;
  translations?: Partial<Record<ContentLanguage, PostText>> | null;
  publish_at?: string | null;
  hide_after?: string | null;
  must_read?: boolean;
  read_count?: number;
  read_by_me?: boolean;
}

interface BackendComment {
  id: number;
  post_id: number;
  author_id: number;
  author_name: string | null;
  author_avatar_color: string | null;
  body: string;
  created_at: string;
  updated_at: string;
  hidden?: boolean;
  reported_by_me?: boolean;
  /** Only for moderators: how often the comment was reported. */
  reports?: number;
}
function stripMarkdown(md: string): string {
  return md
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/~~([^~]+)~~/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/^>\s+/gm, "")
    .replace(/^[-*+]\s+/gm, "")
    .replace(/^\d+\.\s+/gm, "")
    .replace(/^---+$/gm, "")
    .replace(/\n+/g, " ")
    .trim()
}

/** The member's content language: the app's language (de or en). */
export function readerLanguage(): ContentLanguage {
  return (i18n.language || "de").startsWith("en") ? "en" : "de";
}

/** The post in *lang* when it has that language, else as written. */
export function postIn(post: Post, lang: ContentLanguage | null): Post {
  const text = (lang && post.translations[lang]) || null;
  const shown = text ?? post.original;
  return {
    ...post,
    title: shown.title,
    summary: shown.summary,
    body: shown.body,
    snippet: shown.summary ?? stripMarkdown(shown.body).slice(0, 160),
    shownLanguage: text ? lang : post.language,
  };
}

/** Languages the post can be read in, the original first. */
export function postLanguages(post: Post): ContentLanguage[] {
  const others = Object.keys(post.translations) as ContentLanguage[];
  return post.language ? [post.language, ...others] : others.length ? others : [];
}

function adaptPost(b: BackendPost): Post {
  const original = { title: b.title, summary: b.summary, body: b.body };
  const post: Post = {
    id: String(b.id),
    authorId: String(b.author_id),
    author: b.author_name ?? "Unknown",
    avatarColor: b.author_avatar_color ?? "#fece2b",
    ...original,
    snippet: "",
    createdAt: b.created_at,
    time: formatRelative(b.created_at),
    likes: b.like_count,
    likeMemberIds: b.like_member_ids.map(String),
    comments: b.comment_count,
    groupId: b.group_id != null ? String(b.group_id) : null,
    shownLanguage: b.language ?? null,
    language: b.language ?? null,
    original,
    translations: b.translations ?? {},
    publishAt: b.publish_at ?? null,
    hideAfter: b.hide_after ?? null,
    mustRead: b.must_read ?? false,
    readCount: b.read_count ?? 0,
    readByMe: b.read_by_me ?? false,
  };
  return postIn(post, readerLanguage());
}

function adaptComment(b: BackendComment): PostComment {
  return {
    id: String(b.id),
    authorId: String(b.author_id),
    author: b.author_name ?? "Unknown",
    avatarColor: b.author_avatar_color ?? "#fece2b",
    body: b.body,
    createdAt: b.created_at,
    time: formatRelative(b.created_at),
    hidden: !!b.hidden,
    reportedByMe: !!b.reported_by_me,
    reports: b.reports,
  };
}

export async function listPosts(): Promise<Post[]> {
  const data = await apiFetch<BackendPost[]>("/app/posts");
  return data.map(adaptPost);
}

export async function getPost(id: string): Promise<Post> {
  const data = await apiFetch<BackendPost>(`/app/posts/${id}`);
  return adaptPost(data);
}

export interface PostCreate {
  title: string;
  summary?: string;
  body: string;
  /** The group the post is for; empty: the whole club. */
  groupId?: string | null;
  language?: ContentLanguage | null;
  translations?: Partial<Record<ContentLanguage, PostText>> | null;
  /** Scheduled: out at this time (ISO). */
  publishAt?: string | null;
  /** Hidden from members after this time (ISO). */
  hideAfter?: string | null;
  /** Members confirm they read it. */
  mustRead?: boolean;
}

export async function createPost(input: PostCreate): Promise<Post> {
  const data = await apiFetch<BackendPost>("/app/posts/", {
    method: "POST",
    body: JSON.stringify({
      title: input.title,
      summary: input.summary ?? null,
      body: input.body,
      ...(input.language !== undefined ? { language: input.language } : {}),
      ...(input.translations !== undefined ? { translations: input.translations } : {}),
      ...(input.publishAt ? { publish_at: input.publishAt } : {}),
      ...(input.hideAfter ? { hide_after: input.hideAfter } : {}),
      ...(input.mustRead ? { must_read: true } : {}),
      ...(input.groupId !== undefined
        ? { group_id: input.groupId ? Number(input.groupId) : null }
        : {}),
    }),
  });
  return adaptPost(data);
}

export interface PostUpdate {
  title?: string;
  summary?: string;
  body?: string;
  groupId?: string | null;
  language?: ContentLanguage | null;
  translations?: Partial<Record<ContentLanguage, PostText>> | null;
  /** A scheduled post only; null: out now. */
  publishAt?: string | null;
  hideAfter?: string | null;
  mustRead?: boolean;
}

/** Whether the platform set up machine translation. */
export async function getTranslationAvailable(): Promise<{ available: boolean }> {
  return apiFetch("/app/posts/translate");
}

/** Title, summary and text in *target*, to pre-fill the editor. */
export async function machineTranslate(
  target: ContentLanguage,
  source: ContentLanguage | null,
  text: PostText,
): Promise<PostText> {
  return apiFetch("/app/posts/translate", {
    method: "POST",
    body: JSON.stringify({ target, source, ...text }),
  });
}

export async function updatePost(
  id: string,
  input: PostUpdate,
): Promise<Post> {
  const { groupId, publishAt, hideAfter, mustRead, ...rest } = input;
  const body: Record<string, unknown> = { ...rest };
  if (groupId !== undefined) body.group_id = groupId ? Number(groupId) : null;
  if (publishAt !== undefined) body.publish_at = publishAt;
  if (hideAfter !== undefined) body.hide_after = hideAfter;
  if (mustRead !== undefined) body.must_read = mustRead;
  const data = await apiFetch<BackendPost>(`/app/posts/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  return adaptPost(data);
}

export async function deletePost(id: string): Promise<void> {
  await apiFetch(`/app/posts/${id}`, { method: "DELETE" });
}

export async function likePost(id: string): Promise<Post> {
  const data = await apiFetch<BackendPost>(`/app/posts/${id}/like`, {
    method: "POST",
  });
  return adaptPost(data);
}

export async function unlikePost(id: string): Promise<Post> {
  const data = await apiFetch<BackendPost>(`/app/posts/${id}/like`, {
    method: "DELETE",
  });
  return adaptPost(data);
}

export async function listComments(postId: string): Promise<PostComment[]> {
  const data = await apiFetch<BackendComment[]>(`/app/posts/${postId}/comments`);
  return data.map(adaptComment);
}

export async function addComment(
  postId: string,
  body: string,
): Promise<PostComment> {
  const data = await apiFetch<BackendComment>(`/app/posts/${postId}/comments`, {
    method: "POST",
    body: JSON.stringify({ body }),
  });
  return adaptComment(data);
}

export async function deleteComment(
  postId: string,
  commentId: string,
): Promise<void> {
  await apiFetch(`/app/posts/${postId}/comments/${commentId}`, {
    method: "DELETE",
  });
}

/** The member confirms they read a must-read post. */
export async function confirmRead(id: string): Promise<Post> {
  const data = await apiFetch<BackendPost>(`/app/posts/${id}/read`, { method: "POST" });
  return adaptPost(data);
}

export interface ReadStatus {
  confirmed: { member_id: number; name: string; read_at: string }[];
  missing: { member_id: number; name: string }[];
  reminder_sent_at: string | null;
}

/** Who confirmed a must-read post and who has not (those who manage it). */
export async function getReadStatus(id: string): Promise<ReadStatus> {
  return apiFetch<ReadStatus>(`/app/posts/${id}/reads`);
}

// ── Comment moderation ───────────────────────────────────────────────────────

const commentUrl = (postId: string, commentId: string) =>
  `/app/posts/${postId}/comments/${commentId}`;

/** Report a comment to the moderators. */
export async function reportComment(
  postId: string,
  commentId: string,
  reason: string,
): Promise<PostComment> {
  const data = await apiFetch<BackendComment>(`${commentUrl(postId, commentId)}/report`, {
    method: "POST",
    body: JSON.stringify({ reason: reason.trim() || null }),
  });
  return adaptComment(data);
}

/** Moderators: hide a comment, or show it again. */
export async function setCommentHidden(
  postId: string,
  commentId: string,
  hidden: boolean,
): Promise<PostComment> {
  const data = await apiFetch<BackendComment>(
    `${commentUrl(postId, commentId)}/${hidden ? "hide" : "show"}`,
    { method: "POST" },
  );
  return adaptComment(data);
}

/** Moderators: keep a reported comment, its reports are done. */
export async function keepComment(postId: string, commentId: string): Promise<PostComment> {
  const data = await apiFetch<BackendComment>(`${commentUrl(postId, commentId)}/reports`, {
    method: "DELETE",
  });
  return adaptComment(data);
}

export interface ReportedComment {
  comment_id: number;
  post_id: number;
  post_title: string;
  author_id: number;
  author_name: string;
  body: string;
  created_at: string;
  reports: number;
  reasons: string[];
  last_reported_at: string;
}

export interface CommentMute {
  member_id: number;
  member_name: string;
  until: string;
  reason: string | null;
  by_name: string | null;
}

export async function listReportedComments(): Promise<{ items: ReportedComment[] }> {
  return apiFetch("/app/posts/comments/reports");
}

export async function listCommentMutes(): Promise<{ items: CommentMute[] }> {
  return apiFetch("/app/posts/comments/mutes");
}

/** Moderators: the member may not comment for *days* days. */
export async function muteCommenter(
  memberId: string,
  days: number,
  reason: string,
): Promise<{ items: CommentMute[] }> {
  return apiFetch("/app/posts/comments/mutes", {
    method: "POST",
    body: JSON.stringify({ member_id: Number(memberId), days, reason: reason.trim() || null }),
  });
}

export async function unmuteCommenter(memberId: string | number): Promise<{ items: CommentMute[] }> {
  return apiFetch(`/app/posts/comments/mutes/${memberId}`, { method: "DELETE" });
}
