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
  emergencyContact?: { name?: string; phone?: string; relation?: string } | null;
  customFields?: Record<string, unknown> | null;
}

export interface ClubFunction {
  id: number;
  name: string;
  description: string | null;
  maxHolders: number;
  holders: {
    memberId: number;
    memberName: string;
    assignedAt: string | null;
  }[];
}

export interface Group {
  id: string;
  name: string;
  lead: string;
  description: string;
  color: string;
  iconName: string;
  members: number;
  sessions: string;
  tools: number;
  type?: string;
  emailAlias?: string;
  isPublic?: boolean;
  selfJoin?: boolean;
  parentGroupId?: number | null;
  parentGroupName?: string | null;
}

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
  requiresApproval?: boolean;
  isPublic?: boolean;
  coverImageUrl?: string | null;
  color?: string | null;
  registrationCount?: number;
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
  requiredGroupIds?: number[];
  requiredFunctionIds?: number[];
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
}

export interface AuditEntry {
  id: string;
  actor: string;
  action: string;
  target: string;
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
}

export type InventoryCategory = "Tool" | "Item" | "Material";
export type InventoryStatus =
  | "available"
  | "in_use"
  | "maintenance"
  | "broken"
  | "archived"
  | "checked_out"
  | "pending"
  | "lost"
  | "retired";
export type InventoryVisibility = "private" | "shared";

export interface InventoryLink {
  label: string;
  url: string;
}

export interface Code {
  id: string;
  name: string;
  code: string;
  description: string | null;
  isActive: boolean;
  createdBy: string | null;
  updatedBy: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface InventoryItem {
  id: string;
  name: string;
  category: InventoryCategory;
  description: string;
  ownerId: number | null;
  ownerName: string | null;
  responsibleId: number | null;
  responsibleName: string | null;
  visibility: InventoryVisibility;
  status: InventoryStatus;
  cost: string | null;
  links: InventoryLink[];
  instructionRequired: boolean;
  instructedMemberIds: number[];
  instructedMemberNames: string[];
  createdAt: string;
  updatedAt: string;
  purchaseDate?: string;
  purchaseCost?: string | null;
  currentValue?: string | null;
  location?: string;
  serialNumber?: string;
  barcodeId?: string;
  documents?: { name: string; url: string; type?: string }[];
  imageUrl?: string | null;
  notes?: string;
}
