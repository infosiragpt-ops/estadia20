CREATE TABLE `listings` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`category` text NOT NULL,
	`title` text NOT NULL,
	`location` text NOT NULL,
	`description` text DEFAULT '' NOT NULL,
	`image` text DEFAULT '' NOT NULL,
	`gallery` text DEFAULT '[]' NOT NULL,
	`price` integer NOT NULL,
	`price_label` text NOT NULL,
	`rating` real DEFAULT 5 NOT NULL,
	`reviews` integer DEFAULT 0 NOT NULL,
	`meta` text DEFAULT '' NOT NULL,
	`badge` text,
	`owner_name` text NOT NULL,
	`owner_whatsapp` text NOT NULL,
	`service` text,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL
);
