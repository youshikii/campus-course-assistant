-- Non-destructive initialization; requires users and courses tables.
CREATE TABLE IF NOT EXISTS `schedules` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `student_id` INT NOT NULL,
  `course_id` INT NOT NULL,
  `weekday` INT NOT NULL,
  `start_time` TIME NOT NULL,
  `end_time` TIME NOT NULL,
  `start_date` DATE NOT NULL,
  `end_date` DATE NOT NULL,
  `location` VARCHAR(100) NOT NULL DEFAULT '',
  `notes` TEXT NOT NULL,
  `create_time` DATETIME NOT NULL,
  `update_time` DATETIME NOT NULL,
  PRIMARY KEY (`id`),
  INDEX `ix_schedules_student_id` (`student_id`),
  INDEX `ix_schedules_course_id` (`course_id`),
  CONSTRAINT `fk_schedules_student` FOREIGN KEY (`student_id`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_schedules_course` FOREIGN KEY (`course_id`) REFERENCES `courses` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
