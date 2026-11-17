-- Auth and logging tables for the ADS-B API (IA626, username nesarar)

DROP TABLE IF EXISTS `nesarar_api_logs`;
DROP TABLE IF EXISTS `nesarar_auth`;

CREATE TABLE `nesarar_auth` (
    `uid`   INT NOT NULL AUTO_INCREMENT,
    `token` VARCHAR(64) NOT NULL,
    `email` VARCHAR(255) NULL,
    PRIMARY KEY (`uid`),
    UNIQUE KEY `token_unique` (`token`)
);

INSERT INTO `nesarar_auth` (`token`, `email`) VALUES ('123', 'nesarar@clarkson.edu');

CREATE TABLE `nesarar_api_logs` (
    `logid`    INT NOT NULL AUTO_INCREMENT,
    `endpoint` VARCHAR(100) NOT NULL,
    `token`    VARCHAR(64) NULL,
    `response` VARCHAR(50) NOT NULL,
    `dt`       DATETIME NOT NULL,
    PRIMARY KEY (`logid`),
    KEY `token_dt` (`token`, `dt`)
);
