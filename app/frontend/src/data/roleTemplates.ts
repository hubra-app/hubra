export interface RoleTemplatePermission {
  key: string
}

export interface RoleTemplateRole {
  name: string
  description: string
  is_admin: boolean
  permissions: string[]
}

export interface RoleTemplate {
  id: string
  name: string
  description: string
  roles: RoleTemplateRole[]
}

export const ROLE_TEMPLATES: RoleTemplate[] = [
  {
    id: 'standard-club',
    name: 'Standard Club',
    description:
      'A typical club setup with Admin, Board Member, and Member roles.',
    roles: [
      {
        name: 'Admin',
        description: 'Full system access — bypasses all permission checks',
        is_admin: true,
        permissions: [],
      },
      {
        name: 'Board Member',
        description:
          'Elevated access — can manage members, groups, events, and finances',
        is_admin: false,
        permissions: [
          'members.members.read',
          'members.members.create',
          'members.members.update',
          'members.members.archive',
          'members.members.export',
          'groups.groups.read',
          'groups.groups.create',
          'groups.groups.update',
          'groups.groups.add_member',
          'groups.groups.remove_member',
          'events.events.read',
          'events.events.create',
          'events.events.update',
          'events.events.delete',
          'events.events.add_attendee',
          'events.events.remove_attendee',
          'polls.polls.read',
          'polls.polls.create',
          'polls.polls.update',
          'polls.polls.vote',
          'polls.polls.close',
          'posts.posts.read',
          'posts.posts.create',
          'posts.posts.update',
          'posts.posts.comment',
          'posts.posts.like',
          'finance.transactions.read',
          'finance.transactions.create',
          'finance.transactions.update',
          'finance.invoices.read',
          'finance.invoices.create',
          'finance.invoices.update',
          'finance.invoices.remind',
          'finance.overview.read',
          'inventory.items.read',
          'inventory.items.create',
          'inventory.items.update',
        ],
      },
      {
        name: 'Member',
        description: 'Basic read-only access to club resources',
        is_admin: false,
        permissions: [
          'members.members.read',
          'groups.groups.read',
          'events.events.read',
          'polls.polls.read',
          'polls.polls.vote',
          'posts.posts.read',
          'posts.posts.comment',
          'posts.posts.like',
          'inventory.items.read',
        ],
      },
    ],
  },
  {
    id: 'small-association',
    name: 'Small Association',
    description:
      'Minimal setup for small associations — Admin and Member roles only.',
    roles: [
      {
        name: 'Admin',
        description: 'Full system access',
        is_admin: true,
        permissions: [],
      },
      {
        name: 'Member',
        description: 'Can view members, events, and vote on polls',
        is_admin: false,
        permissions: [
          'members.members.read',
          'events.events.read',
          'polls.polls.read',
          'polls.polls.vote',
          'posts.posts.read',
          'posts.posts.comment',
        ],
      },
    ],
  },
  {
    id: 'makerspace',
    name: 'Makerspace',
    description:
      'Makerspace-focused setup with Admin, Operator, and Member roles.',
    roles: [
      {
        name: 'Admin',
        description: 'Full system access',
        is_admin: true,
        permissions: [],
      },
      {
        name: 'Operator',
        description:
          'Can manage inventory, events, and member access — but not finances',
        is_admin: false,
        permissions: [
          'members.members.read',
          'members.members.update',
          'members.members.disable',
          'members.members.enable',
          'groups.groups.read',
          'groups.groups.create',
          'groups.groups.update',
          'events.events.read',
          'events.events.create',
          'events.events.update',
          'events.events.delete',
          'polls.polls.read',
          'polls.polls.create',
          'polls.polls.vote',
          'posts.posts.read',
          'posts.posts.create',
          'posts.posts.update',
          'inventory.items.read',
          'inventory.items.create',
          'inventory.items.update',
          'inventory.items.delete',
          'inventory.items.manage_instructions',
          'codes.codes.read',
          'codes.codes.create',
          'codes.codes.update',
        ],
      },
      {
        name: 'Member',
        description: 'Can view resources, use inventory, and participate',
        is_admin: false,
        permissions: [
          'members.members.read',
          'groups.groups.read',
          'events.events.read',
          'events.events.add_attendee',
          'events.events.remove_attendee',
          'polls.polls.read',
          'polls.polls.vote',
          'posts.posts.read',
          'posts.posts.create',
          'posts.posts.comment',
          'posts.posts.like',
          'inventory.items.read',
          'inventory.items.instruct_self',
          'codes.codes.read',
        ],
      },
    ],
  },
]
