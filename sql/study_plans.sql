-- Non-destructive initialization; requires the users table.
CREATE TABLE IF NOT EXISTS `study_plans` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `title` VARCHAR(120) NOT NULL,
  `content` TEXT NOT NULL,
  `target_date` DATE NULL,
  `status` VARCHAR(20) NOT NULL DEFAULT 'pending',
  `create_time` DATETIME NOT NULL,
  `update_time` DATETIME NOT NULL,
  PRIMARY KEY (`id`),
  INDEX `ix_study_plans_user_id` (`user_id`),
  CONSTRAINT `fk_study_plans_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
