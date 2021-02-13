create table Tests (
	Id INTEGER AUTO_INCREMENT,
    Result VARCHAR(128),
    Test_Date date,
    Result_Date date,
    `Source` VARCHAR(128),
    Reason VARCHAR(1024),
    `Type` VARCHAR(128),
    ON_CAMPUS_RESIDENT_FLAG CHAR(1),
    ResponseId CHAR(17),
    PRIMARY KEY (Id)
);