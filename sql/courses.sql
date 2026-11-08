-- Non-destructive initialization. Existing courses and private document links are preserved.
-- Run after the users table exists. FastAPI / app.init_db also create this table.
CREATE TABLE IF NOT EXISTS `courses` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `name` VARCHAR(100) NOT NULL,
  `teacher` VARCHAR(100) NOT NULL DEFAULT '',
  `location` VARCHAR(100) NOT NULL DEFAULT '',
  `weekday` INT NOT NULL,
  `start_time` TIME NOT NULL,
  `end_time` TIME NOT NULL,
  `start_date` DATE NOT NULL,
  `end_date` DATE NOT NULL,
  `notes` TEXT NOT NULL,
  `create_time` DATETIME NOT NULL,
  `update_time` DATETIME NOT NULL,
  PRIMARY KEY (`id`),
  INDEX `ix_courses_user_id` (`user_id`),
  CONSTRAINT `fk_courses_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
