export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Role = "CUSTOMER" | "AGENT" | "ADMIN";

export interface User {
  id: string;
  name: string;
  email: string;
  phone: string | null;
  role: Role;
}

export interface QuoteBreakdown {
  pickup_zone: { id: string; name: string; code: string };
  drop_zone: { id: string; name: string; code: string };
  volumetric_weight_kg: number;
  chargeable_weight_kg: number;
  base_charge: string;
  cod_surcharge: string;
  total_charge: string;
  applied_rate_per_kg: string;
  minimum_charge_applied: boolean;
}

export interface Order {
  id: string;
  customer_id: string;
  assigned_agent_id: string | null;
  pickup_address: string;
  pickup_pincode: string;
  drop_address: string;
  drop_pincode: string;
  length_cm: string;
  breadth_cm: string;
  height_cm: string;
  actual_weight_kg: string;
  volumetric_weight_kg: string;
  chargeable_weight_kg: string;
  order_type: "B2B" | "B2C";
  payment_type: "PREPAID" | "COD";
  base_charge: string;
  cod_surcharge: string;
  total_charge: string;
  status: OrderStatus;
  delivery_attempt: number;
  scheduled_delivery_date: string | null;
  created_at: string;
  customer_name?: string;
  agent_name?: string;
}

export type OrderStatus =
  | "PENDING"
  | "ASSIGNED"
  | "PICKED_UP"
  | "IN_TRANSIT"
  | "OUT_FOR_DELIVERY"
  | "DELIVERED"
  | "FAILED"
  | "CANCELLED";

export interface TrackingEvent {
  id: string;
  status: OrderStatus;
  remarks: string | null;
  actor_name?: string | null;
  created_at: string;
}

export interface Notification {
  id: string;
  order_id: string | null;
  kind: string;
  title: string;
  message: string;
  read_at: string | null;
  created_at: string;
}

export interface AgentInfo {
  user_id: string;
  name: string;
  email: string;
  phone: string | null;
  availability_status: "AVAILABLE" | "BUSY" | "OFFLINE";
  latitude: string | null;
  longitude: string | null;
  current_zone_id: string | null;
  vehicle_type: string | null;
  active_orders: number;
}
