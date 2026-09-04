/**
 * Fixtures for the test suite.
 *
 * Everything here is typed against `@/types/api`, so the day the API contract
 * changes shape the fixtures stop compiling instead of quietly lying to the tests.
 * Split amounts are produced with the same `splitEqually` the product uses, so a
 * fixture can never disagree with the app about what an equal split looks like.
 *
 * The cast is the hackathon team from the contract, the currency is always RUB,
 * and amounts are in kopecks at realistic Yekaterinburg magnitudes.
 */

import { splitEqually } from "@/lib/money";
import type {
  Activity,
  ActivityType,
  Category,
  Expense,
  ExpenseSplit,
  Group,
  GroupBalances,
  Member,
  Payment,
  SplitMode,
  Transfer,
  UserBalance,
  UserPublic,
} from "@/types/api";

const ISO_NOW = "2026-08-14T10:00:00+00:00";

/** The five demo accounts, in the order the contract fixes them. */
export const TEAM = [
  { name: "Оля", email: "olya@skladchina.ru" },
  { name: "Саша", email: "sasha@skladchina.ru" },
  { name: "Костя", email: "kostya@skladchina.ru" },
  { name: "Максим", email: "maksim@skladchina.ru" },
  { name: "Жора", email: "zhora@skladchina.ru" },
] as const;

let sequence = 0;

function nextId(prefix: string): string {
  sequence += 1;
  return `${prefix}-${String(sequence).padStart(4, "0")}`;
}

/** Call from a `beforeEach` when a test asserts on generated ids. */
export function resetFactorySequence(): void {
  sequence = 0;
}

export function makeUser(overrides: Partial<UserPublic> = {}): UserPublic {
  const id = overrides.id ?? nextId("user");
  const name = overrides.name ?? TEAM[0].name;
  // A team member keeps their real address; anyone else gets a unique one.
  const email = TEAM.find((member) => member.name === name)?.email ?? `${id}@skladchina.ru`;
  return {
    id,
    name,
    email,
    ...overrides,
  };
}

export function makeCategory(overrides: Partial<Category> = {}): Category {
  return {
    id: nextId("category"),
    slug: "groceries",
    name: "Продукты",
    icon: "ShoppingCart",
    sort_order: 2,
    ...overrides,
  };
}

export function makeMember(overrides: Partial<Member> = {}): Member {
  const user = overrides.user ?? makeUser();
  return {
    id: nextId("member"),
    role: "member",
    joined_at: "2026-01-05T09:00:00+00:00",
    ...overrides,
    user,
  };
}

/** A member built straight from a name, for the common "three people" setup. */
export function makeMembers(names: string[]): Member[] {
  return names.map((name, index) =>
    makeMember({
      user: makeUser({ id: `user-${index + 1}`, name }),
      role: index === 0 ? "owner" : "member",
    }),
  );
}

export function makeGroup(overrides: Partial<Group> = {}): Group {
  const id = overrides.id ?? nextId("group");
  return {
    id,
    name: "Квартира на Вайнера",
    description: "Аренда, ЖКХ и всё, что делим на троих.",
    currency: "RUB",
    owner_id: "user-1",
    created_at: "2026-01-05T09:00:00+00:00",
    updated_at: ISO_NOW,
    member_count: 3,
    my_role: "owner",
    my_net_cents: 0,
    total_spending_cents: 0,
    ...overrides,
  };
}

export interface MakeExpenseOptions {
  id?: string;
  title?: string;
  description?: string | null;
  amountCents?: number;
  currency?: string;
  splitMode?: SplitMode;
  category?: Category;
  payer: UserPublic;
  /** Who the expense is split between. Defaults to just the payer. */
  participants?: UserPublic[];
  /** Explicit per-participant amounts; defaults to an equal split. */
  amounts?: number[];
  /** The user the `my_*` fields are computed for, exactly as the server would. */
  viewerId: string;
  groupId?: string;
  occurredAt?: string;
  creator?: UserPublic;
}

/**
 * An expense as the API returns it *to one specific user* — which is why the
 * viewer is required. The `my_*` fields follow the backend's ledger rules:
 * `my_paid_cents` is the whole amount for the payer, `my_share_cents` is that
 * user's split, and the net is the difference.
 */
export function makeExpense(options: MakeExpenseOptions): Expense {
  const {
    payer,
    viewerId,
    amountCents = 350_000,
    currency = "RUB",
    splitMode = "equal",
    participants = [payer],
    groupId = "group-1",
    occurredAt = ISO_NOW,
  } = options;

  const category = options.category ?? makeCategory();
  const amounts = options.amounts ?? splitEqually(amountCents, participants.length);

  const splits: ExpenseSplit[] = participants.map((user, index) => ({
    user_id: user.id,
    user,
    split_mode: splitMode,
    input_value: splitMode === "equal" ? null : String(amounts[index]),
    calculated_amount_cents: amounts[index],
  }));

  const myShare = splits
    .filter((split) => split.user_id === viewerId)
    .reduce((sum, split) => sum + split.calculated_amount_cents, 0);
  const myPaid = payer.id === viewerId ? amountCents : 0;

  return {
    id: options.id ?? nextId("expense"),
    group_id: groupId,
    title: options.title ?? "Пятёрочка",
    description: options.description ?? null,
    amount_cents: amountCents,
    currency,
    split_mode: splitMode,
    category,
    paid_by: payer.id,
    payer,
    created_by: (options.creator ?? payer).id,
    creator: options.creator ?? payer,
    occurred_at: occurredAt,
    created_at: occurredAt,
    updated_at: occurredAt,
    splits,
    my_share_cents: myShare,
    my_paid_cents: myPaid,
    my_net_cents: myPaid - myShare,
  };
}

export function makeUserBalance(
  user: UserPublic,
  netCents: number,
  overrides: Partial<UserBalance> = {},
): UserBalance {
  return {
    user_id: user.id,
    user,
    paid_cents: netCents > 0 ? netCents : 0,
    owed_cents: netCents < 0 ? -netCents : 0,
    net_cents: netCents,
    ...overrides,
  };
}

export function makeTransfer(
  fromUser: UserPublic,
  toUser: UserPublic,
  amountCents: number,
): Transfer {
  return {
    from_user_id: fromUser.id,
    from_user: fromUser,
    to_user_id: toUser.id,
    to_user: toUser,
    amount_cents: amountCents,
  };
}

export function makeGroupBalances(overrides: Partial<GroupBalances> = {}): GroupBalances {
  const me = makeUser({ id: "user-1", name: "Оля" });
  return {
    group_id: "group-1",
    currency: "RUB",
    balances: [makeUserBalance(me, 0)],
    pairwise: [],
    simplified: [],
    me: makeUserBalance(me, 0),
    total_spending_cents: 0,
    ...overrides,
  };
}

export function makePayment(
  fromUser: UserPublic,
  toUser: UserPublic,
  amountCents: number,
  overrides: Partial<Payment> = {},
): Payment {
  return {
    id: nextId("payment"),
    group_id: "group-1",
    from_user_id: fromUser.id,
    from_user: fromUser,
    to_user_id: toUser.id,
    to_user: toUser,
    amount_cents: amountCents,
    currency: "RUB",
    note: null,
    paid_at: ISO_NOW,
    created_at: ISO_NOW,
    ...overrides,
  };
}

export function makeActivity(
  type: ActivityType,
  actor: UserPublic,
  meta: Record<string, unknown> = {},
  overrides: Partial<Activity> = {},
): Activity {
  return {
    id: nextId("activity"),
    group_id: "group-1",
    group_name: "Квартира на Вайнера",
    actor_id: actor.id,
    actor,
    type,
    entity_id: null,
    meta,
    created_at: ISO_NOW,
    ...overrides,
  };
}
