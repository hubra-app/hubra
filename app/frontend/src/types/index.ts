export type Phase = "login" | "bootstrap" | "app";

export type ToastKind = "success" | "info" | "warning" | "error";

export interface Toast {
  id: string;
  kind: ToastKind;
  title: string;
  msg?: string;
}

export interface Notification {
  id: string;
  kind: "info" | "success" | "warning" | "member";
  title: string;
  msg: string;
  time: string;
  read: boolean;
  /** Club app path it is about, e.g. "/app/operations/posts/3". */
  link?: string | null;
}

export interface Member {
  id: string;
  firstName: string;
  lastName: string;
  name: string;
  email: string;
  publicEmail: string;
  tier: string;
  groups: string[];
  roles: string[];
  /** Roles that come with a function the member holds (Kassier gives Treasurer). */
  functionRoles?: { name: string; function: string }[];
  /** Roles that come with a group the member is in. */
  groupRoles?: { name: string; group: string }[];
  /** Roles held for one group only ("Gruppenleitung", nur Jugend). */
  scopedRoles?: { name: string; group: string }[];
  joined: string;
  lastSeen: string;
  status: "active" | "trial" | "inactive" | "suspended";
  isDisabled?: boolean;
  clubUsername?: string | null;
  mustChangePassword?: boolean;
  toolHours: number;
  notes: string;
  avatarColor: string;
  privateEmailVerified: boolean;
  avatar?: string | null;
  profileNote?: string | null;
  phone?: string;
  mobile?: string;
  birthday?: string;
  membershipType?: string;
  membershipUntil?: string;
  address?: {
    street: string;
    houseNo: string;
    postalCode: string;
    city: string;
    country: string;
  };
  emergencyContact?: { name?: string; phone?: string; relation?: string } | null;
  customFields?: Record<string, unknown> | null;
}

export interface ClubFunction {
  id: number;
  name: string;
  description: string | null;
  maxHolders: number;
  /** The first role the function gives (for older callers). */
  grantsRoleId: number | null;
  /** Every role the function gives its holders (Kassier/in gives Vorstand
   *  and Kassier/in). */
  grantsRoleIds: number[];
  /** A group function (Trainer/in): held per group, its roles count there. */
  perGroup: boolean;
  holders: {
    memberId: number;
    memberName: string;
    assignedAt: string | null;
    groupId?: number | null;
    groupName?: string | null;
  }[];
}

export interface Group {
  id: string;
  name: string;
  lead: string;
  /** The group's leader runs it without the club-wide group rights. */
  leadId?: number | null;
  description: string;
  color: string;
  iconName: string;
  members: number;
  sessions: string;
  type?: string;
  emailAlias?: string;
  /** open: members join on their own; private: only members, lead and managers see it. */
  visibility?: GroupVisibility;
  parentGroupId?: number | null;
  parentGroupName?: string | null;
  /** New members join the group. */
  isDefault?: boolean;
  /** The roles everyone in the group holds for the whole club. */
  roleIds?: number[];
  roles?: { id: number; name: string }[];
  /** Tiers whose members are in the group. */
  tierIds?: number[];
  tiers?: { id: number; name: string }[];
}

export type GroupVisibility = "open" | "visible" | "private";

export interface MailMember {
  id: string;
  name: string;
  publicEmail: string;
  mailboxEnabled: boolean;
  forwardingEnabled: boolean;
  retentionDays: number | null;
  wildduckId: string | null;
  mailboxExists?: boolean;
}

export interface ClubEvent {
  id: string;
  title: string;
  date: string;
  time: string;
  location: string;
  type: "Workshop" | "Social" | "Certification" | "Meeting";
  attendees: string[];
  description?: string;
  meetingUrl?: string;
  endDate?: string;
  allDay?: boolean;
  category?: string;
  maxAttendees?: number | null;
  /** Sign-up and sign-off close at these times (ISO, with zone). */
  registrationDeadline?: string | null;
  cancellationDeadline?: string | null;
  requiresApproval?: boolean;
  isPublic?: boolean;
  /** Shown to the member clubs of this association. */
  federationShared?: boolean;
  /** Places for people who aren't members yet (trial training). */
  trialSpots?: number | null;
  coverImageUrl?: string | null;
  color?: string | null;
  registrationCount?: number;
  /** Places taken against maxAttendees (members with their guests). */
  placesTaken?: number;
  /** Sign-ups waiting for an organiser's approval. */
  pendingCount?: number;
  /** Members who answered "Vielleicht" (no place). */
  maybeCount?: number;
  /** Who put the event up; they run it without the club-wide rights. */
  createdById?: number | null;
  /** Called off (still shown, marked), with the organiser's reason. */
  cancelledAt?: string | null;
  cancelReason?: string | null;
  /** The viewer's own sign-up, if any. */
  myStatus?:
    | "registered"
    | "approved"
    | "waitlisted"
    | "pending"
    | "attended"
    | "declined"
    | "maybe"
    | null;
  /** The group the event is for. */
  groupId?: string | null;
  /** A date of a weekly series, and the rule's date it stands for. */
  seriesId?: string | null;
  seriesDate?: string | null;
  recurrence?: Recurrence | null;
}

/** A weekly rule: every `interval`-th week on `weekdays` (Monday 0) until
 * `until`, without `skipDates`. */
export interface Recurrence {
  startDate?: string;
  until: string;
  interval: number;
  weekdays: number[];
  skipDates: string[];
}

export interface Poll {
  id: string;
  question: string;
  options: { label: string; votes: number }[];
  totalVotes: number;
  closesIn: number;
  closesAt?: string;
  status: "open" | "closed";
  createdById?: string;
  isRequired?: boolean;
  allowProxy?: boolean;
  /** Closes once everyone it is for has voted (Umlaufbeschluss). */
  autoClose?: boolean;
  requiredGroupIds?: number[];
  requiredFunctionIds?: number[];
  /** Option index the signed-in member chose; absent until they vote. */
  myVote?: number;
  /** False when the poll is for groups or functions the member is not in. */
  mayVote?: boolean;
  /** The group the poll belongs to; null: the whole club. */
  groupId?: string | null;
}

export interface PostComment {
  id: string;
  authorId: string;
  author: string;
  avatarColor: string;
  body: string;
  createdAt: string;
  time: string;
}

export interface Post {
  id: string;
  authorId: string;
  author: string;
  avatarColor: string;
  title: string;
  summary: string | null;
  body: string;
  snippet: string;
  createdAt: string;
  time: string;
  likes: number;
  likeMemberIds: string[];
  comments: number;
  /** The group the post is for; null: the whole club. */
  groupId: string | null;
  /** The language shown in title/summary/body: the member's, if the post has it. */
  shownLanguage: ContentLanguage | null;
  /** The language the post was written in; null: not said. */
  language: ContentLanguage | null;
  /** The post as written (the editor works on this). */
  original: PostText;
  /** The other languages. */
  translations: Partial<Record<ContentLanguage, PostText>>;
  /** Scheduled: members see the post from this time (ISO); null: out. */
  publishAt: string | null;
  /** Members no longer see the post after this time (ISO). */
  hideAfter: string | null;
  /** Members confirm they read it. */
  mustRead: boolean;
  /** How many confirmed (must-read posts). */
  readCount: number;
  /** Whether the current member confirmed. */
  readByMe: boolean;
}

export type ContentLanguage = "de" | "fr" | "it" | "en";

export interface PostText {
  title: string;
  summary: string | null;
  body: string;
}

export interface TransactionCategory {
  id: string;
  name: string;
  color: string;
  isDefault: boolean;
}

export interface ExternalParty {
  id: string;
  name: string;
  email: string | null;
  addressStreet: string | null;
  addressHouseNo: string | null;
  addressPostalCode: string | null;
  addressCity: string | null;
  addressCountry: string;
  notes: string | null;
}

export interface Transaction {
  id: string;
  date: string;
  description: string;
  category: string;
  member: string;
  amount: number;
  method: string;
  type: "income" | "expense";
  status: "Pending" | "Completed";
  invoiceId: string | null;
  createdAt: string;
  categoryId?: string | null;
  memberName?: string | null;
  memberId?: string | null;
  payeeName?: string | null;
}

export interface Invoice {
  id: string;
  member: string;
  memberId: string | null;
  externalPartyId: string | null;
  externalPartyName: string | null;
  recipientType: "member" | "external";
  recipientName: string;
  purpose: "membership" | "other";
  issued: string;
  due: string;
  amount: number;
  status: "Paid" | "Open" | "Overdue";
  description: string | null;
  /** What a membership invoice covers, when it was billed with a period. */
  periodStart?: string | null;
  periodEnd?: string | null;
  transactionId: string | null;
  createdAt: string;
  reminderSentAt?: string[];
}

export interface Application {
  id: string;
  name: string;
  email: string;
  wantsTier: string;
  appliedAt: string;
  avatarColor: string;
  /** The poster tag the person came from. */
  source: string | null;
}

export interface AuditEntry {
  id: string;
  actor: string;
  action: string;
  target: string;
  /** What the entry is about, without its type ("Anna Muster"). */
  targetLabel?: string;
  time: string;
  avatarColor: string;
}

export interface MembershipTier {
  id: string;
  name: string;
  color: string;
  priceChf: number | null;
  billingCycle: "monthly" | "yearly" | null;
  priceType: "fixed" | "percentage" | "formula";
  percentageValue: number | null;
  coefficient: number | null;
  roundTo: number | null;
  deductTierIds: number[];
  /** The groups the tier's members are in. */
  groupIds?: number[];
  groups?: { id: number; name: string }[];
}

