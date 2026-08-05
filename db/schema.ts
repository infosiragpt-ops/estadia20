import { sql } from "drizzle-orm";
import { index, integer, real, sqliteTable, text, uniqueIndex } from "drizzle-orm/sqlite-core";

export const listings = sqliteTable("listings", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  category: text("category", { enum: ["Roomies", "Depas", "Airbnb", "Transporte"] }).notNull(),
  title: text("title").notNull(),
  location: text("location").notNull(),
  description: text("description").notNull().default(""),
  image: text("image").notNull().default(""),
  gallery: text("gallery").notNull().default("[]"),
  price: integer("price").notNull(),
  priceLabel: text("price_label").notNull(),
  rating: real("rating").notNull().default(5),
  reviews: integer("reviews").notNull().default(0),
  meta: text("meta").notNull().default(""),
  badge: text("badge"),
  ownerName: text("owner_name").notNull(),
  ownerWhatsApp: text("owner_whatsapp").notNull(),
  service: text("service"),
  detailsJson: text("details_json").notNull().default("{}"),
  createdAt: text("created_at").notNull().default(sql`CURRENT_TIMESTAMP`),
}, (table) => ({
  categoryCreatedAtIdx: index("idx_listings_category_created_at").on(table.category, table.createdAt),
}));

export const favorites = sqliteTable("favorites", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  visitorId: text("visitor_id").notNull(),
  listingId: integer("listing_id").notNull(),
  createdAt: text("created_at").notNull().default(sql`CURRENT_TIMESTAMP`),
}, (table) => ({
  visitorListingUnique: uniqueIndex("idx_favorites_visitor_listing").on(table.visitorId, table.listingId),
}));

export const inquiries = sqliteTable("inquiries", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  visitorId: text("visitor_id").notNull(),
  listingId: integer("listing_id").notNull(),
  channel: text("channel").notNull().default("whatsapp"),
  createdAt: text("created_at").notNull().default(sql`CURRENT_TIMESTAMP`),
}, (table) => ({
  listingCreatedAtIdx: index("idx_inquiries_listing_created_at").on(table.listingId, table.createdAt),
}));
