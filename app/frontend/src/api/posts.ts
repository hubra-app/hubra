import { apiFetch } from '@vollbuild/api-client';
import { formatRelative } from "@/format";
import type { Post, PostComment } from "@/types";

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

function adaptPost(b: BackendPost): Post {
  const snippet = b.summary ?? stripMarkdown(b.body).slice(0, 160);
  return {
    id: String(b.id),
    authorId: String(b.author_id),
    author: b.author_name ?? "Unknown",
    avatarColor: b.author_avatar_color ?? "#fece2b",
    title: b.title,
    summary: b.summary,
    body: b.body,
    snippet,
    createdAt: b.created_at,
    time: formatRelative(b.created_at),
    likes: b.like_count,
    likeMemberIds: b.like_member_ids.map(String),
    comments: b.comment_count,
  };
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
  };
}

export async function listPosts(): Promise<Post[]> {
  const data = await apiFetch<BackendPost[]>("/posts");
  return data.map(adaptPost);
}

export async function getPost(id: string): Promise<Post> {
  const data = await apiFetch<BackendPost>(`/posts/${id}`);
  return adaptPost(data);
}

export interface PostCreate {
  title: string;
  summary?: string;
  body: string;
}

export async function createPost(input: PostCreate): Promise<Post> {
  const data = await apiFetch<BackendPost>("/posts/", {
    method: "POST",
    body: JSON.stringify({
      title: input.title,
      summary: input.summary ?? null,
      body: input.body,
    }),
  });
  return adaptPost(data);
}

export interface PostUpdate {
  title?: string;
  summary?: string;
  body?: string;
}

export async function updatePost(
  id: string,
  input: PostUpdate,
): Promise<Post> {
  const data = await apiFetch<BackendPost>(`/posts/${id}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
  return adaptPost(data);
}

export async function deletePost(id: string): Promise<void> {
  await apiFetch(`/posts/${id}`, { method: "DELETE" });
}

export async function likePost(id: string): Promise<Post> {
  const data = await apiFetch<BackendPost>(`/posts/${id}/like`, {
    method: "POST",
  });
  return adaptPost(data);
}

export async function unlikePost(id: string): Promise<Post> {
  const data = await apiFetch<BackendPost>(`/posts/${id}/like`, {
    method: "DELETE",
  });
  return adaptPost(data);
}

export async function listComments(postId: string): Promise<PostComment[]> {
  const data = await apiFetch<BackendComment[]>(`/posts/${postId}/comments`);
  return data.map(adaptComment);
}

export async function addComment(
  postId: string,
  body: string,
): Promise<PostComment> {
  const data = await apiFetch<BackendComment>(`/posts/${postId}/comments`, {
    method: "POST",
    body: JSON.stringify({ body }),
  });
  return adaptComment(data);
}

export async function deleteComment(
  postId: string,
  commentId: string,
): Promise<void> {
  await apiFetch(`/posts/${postId}/comments/${commentId}`, {
    method: "DELETE",
  });
}
