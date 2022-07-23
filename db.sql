-- Adminer 4.8.1 MySQL 10.9.1-MariaDB dump

SET NAMES utf8;
SET time_zone = '+00:00';
SET foreign_key_checks = 0;

SET NAMES utf8mb4;

CREATE DATABASE `wallstreet-votes` /*!40100 DEFAULT CHARACTER SET utf8mb4 */;
USE `wallstreet-votes`;

CREATE TABLE `leader_votes` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `candidate` int(11) NOT NULL,
  `voter` int(11) NOT NULL,
  `direction` tinyint(1) NOT NULL COMMENT '1 is up, -1 is down',
  `time` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `candidate` (`candidate`),
  KEY `voter` (`voter`),
  CONSTRAINT `leader_votes_ibfk_1` FOREIGN KEY (`candidate`) REFERENCES `users` (`id`),
  CONSTRAINT `leader_votes_ibfk_2` FOREIGN KEY (`voter`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


CREATE TABLE `stocks` (
  `ticker_direction` varchar(7) NOT NULL COMMENT 'ticker_1 is long, 0 is short',
  `description` text NOT NULL,
  `votes` int(11) NOT NULL DEFAULT 0 COMMENT 'up-down',
  `total_votes` int(11) NOT NULL DEFAULT 0 COMMENT 'up+down',
  `posted_by` int(11) NOT NULL,
  PRIMARY KEY (`ticker_direction`),
  KEY `posted_by_votes` (`posted_by`,`votes` DESC),
  CONSTRAINT `stocks_ibfk_3` FOREIGN KEY (`posted_by`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


CREATE TABLE `stock_votes` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `ticker_direction` varchar(7) NOT NULL COMMENT 'ticker_1 is long, 0 is short',
  `voter` int(11) NOT NULL,
  `direction` tinyint(1) NOT NULL COMMENT '1 is up, -1 is down',
  `time` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `voter` (`voter`),
  KEY `ticker_direction` (`ticker_direction`),
  CONSTRAINT `stock_votes_ibfk_2` FOREIGN KEY (`voter`) REFERENCES `users` (`id`),
  CONSTRAINT `stock_votes_ibfk_3` FOREIGN KEY (`ticker_direction`) REFERENCES `stocks` (`ticker_direction`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


CREATE TABLE `users` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `username` text NOT NULL,
  `password` varchar(128) NOT NULL COMMENT 'SHA512 fixed length 128',
  `leader_votes` int(11) NOT NULL DEFAULT 0,
  `total_leader_votes` int(11) NOT NULL DEFAULT 0,
  `is_leader` tinyint(1) NOT NULL DEFAULT 0 COMMENT '1 is yes, 0 is no',
  `register_time` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`) USING HASH
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- 2022-07-23 14:56:20