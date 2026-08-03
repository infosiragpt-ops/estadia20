import { sql } from "drizzle-orm";
import { index, integer, real, sqliteTable, text } from "drizzle-orm/sqlite-core";

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
  createdAt: text("created_at").notNull().default(sql`CURRENT_TIMESTAMP`),
}, (table) => ({
  categoryCreatedAtIdx: index("idx_listings_category_created_at").on(table.category, table.createdAt),
}));
