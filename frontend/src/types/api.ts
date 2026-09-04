/**
 * The single declaration of every API shape.
 *
 * This mirrors section 7 of docs/contract.md. Money is always an integer number of
 * minor units (cents) in a field ending in `_cents` — no decimal money crosses the
 * wire, so nothing here needs float-safe parsing. Use `src/lib/money.ts` to render it.
 */

export type Uuid = string;
/** ISO-8601 with offset, e.g. `2026-08-14T10:00:00+00:00`. */
export type IsoDateTime = string;

export type GroupRole = "owner" | "member";
export type SplitMode = "equal" | "exact" | "percentage" | "shares";
export type InviteStatus = "pending" | "accepted" | "expired";

export type ActivityType =
  | "group_created"
  | "group_updated"
  | "member_joined"
  | "member_removed"
  | "expense_created"
  | "expense_updated"
  | "expense_deleted"
  | "payment_created"
  | "invite_created"
  | "debt_simplified";

export type DashboardPeriod =
  | "all"
  | "this_month"
  | "last_month"
  | "last_3_months"
  | "custom";

export interface UserPublic {
  id: Uuid;
  name: string;
  email: string;
}

export interface Category {
  id: Uuid;
  slug: string;
  name: string;
  icon: string;
  sort_order: number;
}

export interface Member {
  id: Uuid;
  user: UserPublic;
  role: GroupRole;
  joined_at: IsoDateTime;
}

export interface Group {
  id: Uuid;
  name: string;
  description: string | null;
  currency: string;
  owner_id: Uuid;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
  member_count: number;
  my_role: GroupRole;
  my_net_cents: number;
  total_spending_cents: number;
}

export interface ExpenseSplit {
  user_id: Uuid;
  user: UserPublic;
  split_mode: SplitMode;
  /** Whatever the user typed: cents for `exact`, percent, or share count. */
  input_value: string | null;
  calculated_amount_cents: number;
}

export interface Expense {
  id: Uuid;
  group_id: Uuid;
  title: string;
  description: string | null;
  amount_cents: number;
  currency: string;
  split_mode: SplitMode;
  category: Category;
  paid_by: Uuid;
  payer: UserPublic;
  created_by: Uuid;
  creator: UserPublic;
  occurred_at: IsoDateTime;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
  splits: ExpenseSplit[];
  my_share_cents: number;
  my_paid_cents: number;
  my_net_cents: number;
}

export interface ExpensePage {
  items: Expense[];
  total: number;
  limit: number;
  offset: number;
}

export interface UserBalance {
  user_id: Uuid;
  user: UserPublic;
  paid_cents: number;
  owed_cents: number;
  net_cents: number;
}

export interface Transfer {
  from_user_id: Uuid;
  from_user: UserPublic;
  to_user_id: Uuid;
  to_user: UserPublic;
  amount_cents: number;
}

export interface GroupBalances {
  group_id: Uuid;
  currency: string;
  balances: UserBalance[];
  pairwise: Transfer[];
  simplified: Transfer[];
  me: UserBalance;
  total_spending_cents: number;
}

export interface SimplifyPreview {
  current_transfer_count: number;
  simplified_transfer_count: number;
  current_transfers: Transfer[];
  transfers: Transfer[];
}

export interface Payment {
  id: Uuid;
  group_id: Uuid;
  from_user_id: Uuid;
  from_user: UserPublic;
  to_user_id: Uuid;
  to_user: UserPublic;
  amount_cents: number;
  currency: string;
  note: string | null;
  paid_at: IsoDateTime;
  created_at: IsoDateTime;
}

export interface Activity {
  id: Uuid;
  group_id: Uuid;
  group_name: string;
  actor_id: Uuid;
  actor: UserPublic;
  type: ActivityType;
  entity_id: Uuid | null;
  meta: Record<string, unknown>;
  created_at: IsoDateTime;
}

export interface InviteGroupPreview {
  id: Uuid;
  name: string;
  description: string | null;
  currency: string;
  member_count: number;
}

export interface InvitePreview {
  group: InviteGroupPreview;
  inviter: UserPublic;
  invited_email: string;
  expires_at: IsoDateTime;
  status: InviteStatus;
  already_member: boolean;
}

export interface InviteCreated {
  id: Uuid;
  group_id: Uuid;
  invited_email: string;
  /** Returned exactly once, at creation. Only its hash is stored server-side. */
  token: string;
  invite_url: string;
  expires_at: IsoDateTime;
  created_at: IsoDateTime;
}

export interface Invite {
  id: Uuid;
  group_id: Uuid;
  invited_email: string;
  inviter: UserPublic;
  expires_at: IsoDateTime;
  accepted_at: IsoDateTime | null;
  status: InviteStatus;
  created_at: IsoDateTime;
}

export interface DashboardGroupSummary {
  group_id: Uuid;
  name: string;
  currency: string;
  net_cents: number;
  total_spending_cents: number;
  /** Доля смотрящего в расходах группы за период — под полосу в карточке. */
  your_share_cents: number;
  member_count: number;
}

export interface DashboardSummary {
  you_owe_cents: number;
  owed_to_you_cents: number;
  net_cents: number;
  total_spending_cents: number;
  your_paid_cents: number;
  your_share_cents: number;
  group_count: number;
  expense_count: number;
  currency: string;
  groups: DashboardGroupSummary[];
}

export interface CategoryBreakdownItem {
  category_id: Uuid;
  slug: string;
  name: string;
  icon: string;
  amount_cents: number;
  percentage: number;
  expense_count: number;
}

export interface CategoryBreakdown {
  total_cents: number;
  items: CategoryBreakdownItem[];
}

export interface SpendingOverTimePoint {
  /** `2026-08` */
  month: string;
  /** `Aug 2026` */
  label: string;
  amount_cents: number;
  your_share_cents: number;
}

export interface SpendingOverTime {
  currency: string;
  items: SpendingOverTimePoint[];
}

export type SavingTipType = "data_driven" | "generic";

export interface SavingTip {
  title: string;
  text: string;
  type: SavingTipType;
}

export interface SavingTipsResponse {
  tips: SavingTip[];
}

/* ---------------------------------- inputs --------------------------------- */

export interface RegisterInput {
  name: string;
  email: string;
  password: string;
}

export interface LoginInput {
  email: string;
  password: string;
}

export interface UpdateMeInput {
  name?: string;
  email?: string;
}

export interface ChangePasswordInput {
  current_password: string;
  new_password: string;
}

export interface GroupCreateInput {
  name: string;
  description?: string | null;
  currency?: string;
}

export interface GroupUpdateInput {
  name?: string;
  description?: string | null;
  currency?: string;
}

export interface ParticipantInput {
  user_id: Uuid;
  /** Cents for `exact`, percent for `percentage`, count for `shares`, null for `equal`. */
  value: string | null;
}

export interface ExpenseCreateInput {
  title: string;
  description?: string | null;
  amount_cents: number;
  category_id: Uuid;
  paid_by: Uuid;
  occurred_at: IsoDateTime;
  split_mode: SplitMode;
  participants: ParticipantInput[];
}

export type ExpenseUpdateInput = Partial<ExpenseCreateInput>;

export interface PaymentCreateInput {
  from_user_id: Uuid;
  to_user_id: Uuid;
  amount_cents: number;
  note?: string | null;
  paid_at?: IsoDateTime;
}

export interface ExpenseFilters {
  category_id?: Uuid;
  paid_by?: Uuid;
  date_from?: string;
  date_to?: string;
  q?: string;
  limit?: number;
  offset?: number;
}

export interface DashboardParams {
  period?: DashboardPeriod;
  date_from?: string;
  date_to?: string;
  group_id?: Uuid;
}

// ------------------------------------------------------------------ voice expenses

export type ResolutionStatus = "resolved" | "ambiguous" | "unresolved";

/**
 * One field the voice pipeline extracted, resolved against real group data —
 * or not. `resolved` carries `value`; `ambiguous` carries `candidates` (more
 * than one plausible match); `unresolved` carries neither. The UI must never
 * guess for the last two — it asks the user to pick explicitly.
 */
export interface FieldResolution<T> {
  status: ResolutionStatus;
  value: T | null;
  candidates: T[];
  raw_text: string | null;
}

export interface AmbiguousParticipant {
  raw_text: string;
  candidates: Member[];
}

/**
 * A participant matched unambiguously to a real member, with their share.
 * `value` is `null` for an `equal` split or when the transcript never stated
 * it; otherwise its unit follows the draft's `split_mode` exactly like
 * `ParticipantInput.value` does for a manually entered expense: rubles for
 * `exact`, a percentage for `percentage`, a share count for `shares`.
 */
export interface ResolvedParticipant {
  member: Member;
  value: string | null;
}

export interface ParticipantsResolution {
  resolved: ResolvedParticipant[];
  ambiguous: AmbiguousParticipant[];
  unresolved: string[];
}

/** Ephemeral draft from `POST /groups/{id}/voice-expenses` — never persisted. */
export interface VoiceExpenseDraft {
  transcript: string;
  title: string | null;
  description: string | null;
  amount_cents: number | null;
  occurred_at: IsoDateTime | null;
  split_mode: SplitMode;
  payer: FieldResolution<Member>;
  participants: ParticipantsResolution;
  category: FieldResolution<Category>;
  warnings: string[];
}
