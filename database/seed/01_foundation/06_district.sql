-- =====================================================
-- NSS ERP
-- Module: Foundation
-- Seed File: 06_district.sql
-- Version: 3.0
-- Authority: SOL-FND-004 §15, SOL-ARCH-010 §8
-- Owner: NSS_ADMIN
-- Note: All districts for all Indian states/UTs.
--       Major subdivisions for other seeded countries.
-- =====================================================

-- =========================================================
-- INDIA — ODISHA (30 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('ANG', 'Angul',            1),
    ('BLG', 'Balangir',         2),
    ('BLS', 'Balasore',         3),
    ('BGH', 'Bargarh',          4),
    ('BDK', 'Bhadrak',          5),
    ('BOU', 'Boudh',            6),
    ('CTC', 'Cuttack',          7),
    ('DEB', 'Deogarh',          8),
    ('DHK', 'Dhenkanal',        9),
    ('GJP', 'Gajapati',        10),
    ('GJM', 'Ganjam',          11),
    ('JPR', 'Jagatsinghpur',   12),
    ('AJP', 'Jajpur',          13),
    ('JHR', 'Jharsuguda',      14),
    ('KLH', 'Kalahandi',       15),
    ('KDP', 'Kandhamal',       16),
    ('KDR', 'Kendrapara',      17),
    ('KJH', 'Kendujhar',       18),
    ('KHD', 'Khordha',         19),
    ('KRP', 'Koraput',         20),
    ('MKG', 'Malkangiri',      21),
    ('MBJ', 'Mayurbhanj',      22),
    ('NBR', 'Nabarangpur',     23),
    ('NYG', 'Nayagarh',        24),
    ('NPN', 'Nuapada',         25),
    ('PUR', 'Puri',            26),
    ('RYG', 'Rayagada',        27),
    ('SMP', 'Sambalpur',       28),
    ('SOA', 'Subarnapur',      29),
    ('SDG', 'Sundargarh',      30)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'OD';

-- =========================================================
-- INDIA — ANDHRA PRADESH (26 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('ALV', 'Alluri Sitharama Raju', 1),
    ('ANA', 'Anakapalli',            2),
    ('ANN', 'Annamayya',             3),
    ('ANT', 'Ananthapuramu',         4),
    ('BAP', 'Bapatla',               5),
    ('CHT', 'Chittoor',              6),
    ('EGD', 'East Godavari',         7),
    ('ELU', 'Eluru',                 8),
    ('GUN', 'Guntur',                9),
    ('KDP', 'Kadapa',               10),
    ('KAK', 'Kakinada',             11),
    ('KNL', 'Kurnool',              12),
    ('KRS', 'Krishna',              13),
    ('KON', 'Konaseema',            14),
    ('NAN', 'Nandyal',              15),
    ('NTR', 'NTR',                  16),
    ('NEL', 'Nellore',              17),
    ('PAL', 'Palnadu',              18),
    ('PRK', 'Prakasam',             19),
    ('SPS', 'Sri Potti Sriramulu Nellore', 20),
    ('SRI', 'Srikakulam',           21),
    ('TPT', 'Tirupati',             22),
    ('VIS', 'Visakhapatnam',        23),
    ('VIZ', 'Vizianagaram',         24),
    ('WGD', 'West Godavari',        25),
    ('PAR', 'Parvathipuram Manyam', 26)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'AP';

-- =========================================================
-- INDIA — ARUNACHAL PRADESH (26 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('ANJ', 'Anjaw',                1),
    ('CHA', 'Changlang',            2),
    ('DIB', 'Dibang Valley',        3),
    ('EKM', 'East Kameng',          4),
    ('ESI', 'East Siang',           5),
    ('ICH', 'Itanagar Capital',     6),
    ('KAM', 'Kamle',                7),
    ('KRA', 'Kra Daadi',            8),
    ('KUR', 'Kurung Kumey',         9),
    ('LEP', 'Lepa Rada',           10),
    ('LOH', 'Lohit',               11),
    ('LDV', 'Lower Dibang Valley', 12),
    ('LSI', 'Lower Siang',        13),
    ('LSU', 'Lower Subansiri',     14),
    ('LNG', 'Longding',            15),
    ('NMC', 'Namsai',              16),
    ('PKE', 'Pakke Kessang',       17),
    ('PPG', 'Papum Pare',          18),
    ('SHI', 'Shi Yomi',           19),
    ('SIA', 'Siang',               20),
    ('TAW', 'Tawang',              21),
    ('TIR', 'Tirap',               22),
    ('USI', 'Upper Siang',         23),
    ('USU', 'Upper Subansiri',     24),
    ('WKM', 'West Kameng',         25),
    ('WSI', 'West Siang',          26)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'AR';

-- =========================================================
-- INDIA — ASSAM (35 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('BAK', 'Baksa',            1),
    ('BAR', 'Barpeta',          2),
    ('BIS', 'Biswanath',        3),
    ('BON', 'Bongaigaon',       4),
    ('CAC', 'Cachar',           5),
    ('CHR', 'Charaideo',        6),
    ('CHI', 'Chirang',          7),
    ('DAR', 'Darrang',          8),
    ('DHE', 'Dhemaji',          9),
    ('DHU', 'Dhubri',          10),
    ('DIB', 'Dibrugarh',       11),
    ('DIM', 'Dima Hasao',      12),
    ('GOA', 'Goalpara',        13),
    ('GOL', 'Golaghat',        14),
    ('HAI', 'Hailakandi',      15),
    ('HJO', 'Hojai',           16),
    ('JOR', 'Jorhat',          17),
    ('KAM', 'Kamrup',          18),
    ('KMM', 'Kamrup Metropolitan', 19),
    ('KAN', 'Karbi Anglong',   20),
    ('KAR', 'Karimganj',       21),
    ('KOK', 'Kokrajhar',       22),
    ('LAK', 'Lakhimpur',       23),
    ('MAJ', 'Majuli',          24),
    ('MOR', 'Morigaon',        25),
    ('NAG', 'Nagaon',          26),
    ('NAL', 'Nalbari',         27),
    ('SIB', 'Sivasagar',       28),
    ('SON', 'Sonitpur',        29),
    ('SKA', 'South Salmara-Mankachar', 30),
    ('TAM', 'Tamulpur',        31),
    ('TIN', 'Tinsukia',        32),
    ('UDA', 'Udalguri',        33),
    ('WKA', 'West Karbi Anglong', 34),
    ('BAJ', 'Bajali',          35)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'AS';

-- =========================================================
-- INDIA — BIHAR (38 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('ARA', 'Araria',           1),
    ('ARW', 'Arwal',            2),
    ('AUR', 'Aurangabad',       3),
    ('BAN', 'Banka',            4),
    ('BEG', 'Begusarai',        5),
    ('BHA', 'Bhagalpur',        6),
    ('BHO', 'Bhojpur',          7),
    ('BUX', 'Buxar',            8),
    ('DAR', 'Darbhanga',        9),
    ('ECP', 'East Champaran',  10),
    ('GAY', 'Gaya',            11),
    ('GOP', 'Gopalganj',       12),
    ('JAM', 'Jamui',           13),
    ('JEH', 'Jehanabad',       14),
    ('KAI', 'Kaimur',          15),
    ('KAT', 'Katihar',         16),
    ('KHG', 'Khagaria',        17),
    ('KIS', 'Kishanganj',      18),
    ('LAK', 'Lakhisarai',      19),
    ('MDH', 'Madhepura',       20),
    ('MDB', 'Madhubani',       21),
    ('MUN', 'Munger',          22),
    ('MUZ', 'Muzaffarpur',     23),
    ('NAL', 'Nalanda',         24),
    ('NAW', 'Nawada',          25),
    ('PAT', 'Patna',           26),
    ('PUR', 'Purnia',          27),
    ('ROH', 'Rohtas',          28),
    ('SAH', 'Saharsa',         29),
    ('SAM', 'Samastipur',      30),
    ('SAR', 'Saran',           31),
    ('SHE', 'Sheikhpura',     32),
    ('SHO', 'Sheohar',        33),
    ('SIT', 'Sitamarhi',       34),
    ('SIW', 'Siwan',           35),
    ('SUP', 'Supaul',          36),
    ('VAI', 'Vaishali',        37),
    ('WCP', 'West Champaran',  38)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'BR';

-- =========================================================
-- INDIA — CHHATTISGARH (33 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('BAL', 'Balod',                1),
    ('BLP', 'Baloda Bazar',         2),
    ('BLR', 'Balrampur',            3),
    ('BST', 'Bastar',               4),
    ('BEM', 'Bemetara',             5),
    ('BIJ', 'Bijapur',              6),
    ('BIL', 'Bilaspur',             7),
    ('DAN', 'Dantewada',            8),
    ('DHM', 'Dhamtari',             9),
    ('DUR', 'Durg',                10),
    ('GPB', 'Gariaband',           11),
    ('GRR', 'Gaurela-Pendra-Marwahi', 12),
    ('JAN', 'Janjgir-Champa',      13),
    ('JAS', 'Jashpur',             14),
    ('KBR', 'Kabirdham',           15),
    ('KAN', 'Kanker',              16),
    ('KHA', 'Khairagarh-Chhuikhadan-Gandai', 17),
    ('KOD', 'Kondagaon',           18),
    ('KOR', 'Korba',               19),
    ('KRI', 'Koriya',              20),
    ('MAH', 'Mahasamund',          21),
    ('MAN', 'Manendragarh-Chirmiri-Bharatpur', 22),
    ('MOH', 'Mohla-Manpur-Ambagarh Chowki', 23),
    ('MUN', 'Mungeli',             24),
    ('NAR', 'Narayanpur',          25),
    ('RAI', 'Raipur',              26),
    ('RGR', 'Raigarh',             27),
    ('RJN', 'Rajnandgaon',         28),
    ('SAK', 'Sakti',               29),
    ('SAR', 'Sarangarh-Bilaigarh', 30),
    ('SUK', 'Sukma',               31),
    ('SUR', 'Surajpur',            32),
    ('SGJ', 'Surguja',             33)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'CG';

-- =========================================================
-- INDIA — GOA (2 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('NGO', 'North Goa', 1),
    ('SGO', 'South Goa', 2)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'GA';

-- =========================================================
-- INDIA — GUJARAT (33 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('AHM', 'Ahmedabad',       1),
    ('AMR', 'Amreli',          2),
    ('ANA', 'Anand',           3),
    ('ARV', 'Aravalli',        4),
    ('BAN', 'Banaskantha',     5),
    ('BHA', 'Bharuch',         6),
    ('BHV', 'Bhavnagar',       7),
    ('BOT', 'Botad',           8),
    ('CHH', 'Chhota Udaipur',  9),
    ('DAH', 'Dahod',          10),
    ('DAN', 'Dang',           11),
    ('DEV', 'Devbhumi Dwarka',12),
    ('GAN', 'Gandhinagar',    13),
    ('GIR', 'Gir Somnath',    14),
    ('JAM', 'Jamnagar',       15),
    ('JUN', 'Junagadh',       16),
    ('KAC', 'Kachchh',        17),
    ('KHE', 'Kheda',          18),
    ('MAH', 'Mahisagar',      19),
    ('MEH', 'Mehsana',        20),
    ('MOR', 'Morbi',          21),
    ('NAR', 'Narmada',        22),
    ('NAV', 'Navsari',        23),
    ('PAN', 'Panchmahal',     24),
    ('PAT', 'Patan',          25),
    ('POR', 'Porbandar',      26),
    ('RAJ', 'Rajkot',         27),
    ('SAB', 'Sabarkantha',    28),
    ('SUR', 'Surat',          29),
    ('SRN', 'Surendranagar',  30),
    ('TAP', 'Tapi',           31),
    ('VAD', 'Vadodara',       32),
    ('VAL', 'Valsad',         33)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'GJ';

-- =========================================================
-- INDIA — HARYANA (22 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('AMB', 'Ambala',          1),
    ('BHI', 'Bhiwani',         2),
    ('CHA', 'Charkhi Dadri',   3),
    ('FAR', 'Faridabad',       4),
    ('FAT', 'Fatehabad',       5),
    ('GUR', 'Gurugram',        6),
    ('HIS', 'Hisar',           7),
    ('JHA', 'Jhajjar',         8),
    ('JIN', 'Jind',            9),
    ('KAI', 'Kaithal',        10),
    ('KAR', 'Karnal',         11),
    ('KUR', 'Kurukshetra',    12),
    ('MAH', 'Mahendragarh',   13),
    ('NUH', 'Nuh',            14),
    ('PAL', 'Palwal',         15),
    ('PAN', 'Panchkula',      16),
    ('PNP', 'Panipat',        17),
    ('REW', 'Rewari',         18),
    ('ROH', 'Rohtak',         19),
    ('SIR', 'Sirsa',          20),
    ('SON', 'Sonipat',        21),
    ('YAM', 'Yamunanagar',    22)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'HR';

-- =========================================================
-- INDIA — HIMACHAL PRADESH (12 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('BIL', 'Bilaspur',        1),
    ('CHA', 'Chamba',          2),
    ('HAM', 'Hamirpur',        3),
    ('KAN', 'Kangra',          4),
    ('KIN', 'Kinnaur',         5),
    ('KUL', 'Kullu',           6),
    ('LAH', 'Lahaul and Spiti', 7),
    ('MAN', 'Mandi',           8),
    ('SHI', 'Shimla',          9),
    ('SIR', 'Sirmaur',        10),
    ('SOL', 'Solan',          11),
    ('UNA', 'Una',            12)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'HP';

-- =========================================================
-- INDIA — JHARKHAND (24 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('BOK', 'Bokaro',           1),
    ('CHA', 'Chatra',           2),
    ('DEO', 'Deoghar',          3),
    ('DHN', 'Dhanbad',          4),
    ('DUM', 'Dumka',            5),
    ('EAS', 'East Singhbhum',   6),
    ('GAR', 'Garhwa',           7),
    ('GIR', 'Giridih',          8),
    ('GOD', 'Godda',            9),
    ('GUM', 'Gumla',           10),
    ('HAZ', 'Hazaribagh',      11),
    ('JAM', 'Jamtara',         12),
    ('KHU', 'Khunti',          13),
    ('KOD', 'Koderma',         14),
    ('LAT', 'Latehar',         15),
    ('LOH', 'Lohardaga',       16),
    ('PAK', 'Pakur',           17),
    ('PAL', 'Palamu',          18),
    ('RAM', 'Ramgarh',         19),
    ('RAN', 'Ranchi',          20),
    ('SAH', 'Sahebganj',       21),
    ('SER', 'Seraikela Kharsawan', 22),
    ('SIM', 'Simdega',         23),
    ('WES', 'West Singhbhum',  24)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'JH';

-- =========================================================
-- INDIA — KARNATAKA (31 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('BGL', 'Bagalkot',             1),
    ('BLU', 'Bengaluru Urban',      2),
    ('BLR', 'Bengaluru Rural',      3),
    ('BEL', 'Belagavi',             4),
    ('BLY', 'Ballari',              5),
    ('BID', 'Bidar',                6),
    ('CKM', 'Chamarajanagar',       7),
    ('CKB', 'Chikkaballapura',      8),
    ('CKG', 'Chikkamagaluru',       9),
    ('CTD', 'Chitradurga',         10),
    ('DVG', 'Davangere',           11),
    ('DWD', 'Dharwad',             12),
    ('GAD', 'Gadag',               13),
    ('HAS', 'Hassan',              14),
    ('HVR', 'Haveri',              15),
    ('KLB', 'Kalaburagi',          16),
    ('KDG', 'Kodagu',              17),
    ('KOL', 'Kolar',               18),
    ('KOP', 'Koppal',              19),
    ('MND', 'Mandya',              20),
    ('MYS', 'Mysuru',              21),
    ('RCR', 'Raichur',             22),
    ('RAM', 'Ramanagara',          23),
    ('SMG', 'Shivamogga',          24),
    ('TUM', 'Tumakuru',            25),
    ('UDP', 'Udupi',              26),
    ('UKD', 'Uttara Kannada',      27),
    ('VJN', 'Vijayapura',          28),
    ('YAD', 'Yadgir',             29),
    ('DKN', 'Dakshina Kannada',    30),
    ('VBN', 'Vijayanagara',        31)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'KA';

-- =========================================================
-- INDIA — KERALA (14 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('ALP', 'Alappuzha',        1),
    ('ERN', 'Ernakulam',        2),
    ('IDU', 'Idukki',           3),
    ('KAN', 'Kannur',           4),
    ('KAS', 'Kasaragod',        5),
    ('KOL', 'Kollam',           6),
    ('KOT', 'Kottayam',         7),
    ('KOZ', 'Kozhikode',        8),
    ('MAL', 'Malappuram',       9),
    ('PAL', 'Palakkad',        10),
    ('PTN', 'Pathanamthitta',  11),
    ('TVM', 'Thiruvananthapuram', 12),
    ('TSR', 'Thrissur',        13),
    ('WYD', 'Wayanad',         14)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'KL';

-- =========================================================
-- INDIA — MADHYA PRADESH (55 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('AGR', 'Agar Malwa',       1),
    ('ALI', 'Alirajpur',        2),
    ('ANU', 'Anuppur',          3),
    ('ASH', 'Ashoknagar',       4),
    ('BAL', 'Balaghat',         5),
    ('BAR', 'Barwani',          6),
    ('BET', 'Betul',            7),
    ('BHI', 'Bhind',            8),
    ('BHO', 'Bhopal',           9),
    ('BUR', 'Burhanpur',       10),
    ('CHH', 'Chhatarpur',      11),
    ('CHI', 'Chhindwara',      12),
    ('DAM', 'Damoh',           13),
    ('DAT', 'Datia',           14),
    ('DEW', 'Dewas',           15),
    ('DHA', 'Dhar',            16),
    ('DIN', 'Dindori',         17),
    ('GUN', 'Guna',            18),
    ('GWL', 'Gwalior',         19),
    ('HAR', 'Harda',           20),
    ('HOS', 'Hoshangabad',     21),
    ('IND', 'Indore',          22),
    ('JAB', 'Jabalpur',        23),
    ('JHA', 'Jhabua',          24),
    ('KAT', 'Katni',           25),
    ('KHD', 'Khandwa',         26),
    ('KHG', 'Khargone',        27),
    ('MAN', 'Mandla',          28),
    ('MDS', 'Mandsaur',        29),
    ('MOR', 'Morena',          30),
    ('NAR', 'Narsinghpur',     31),
    ('NEE', 'Neemuch',         32),
    ('NWD', 'Niwari',          33),
    ('PAN', 'Panna',           34),
    ('RAI', 'Raisen',          35),
    ('RAJ', 'Rajgarh',         36),
    ('RAT', 'Ratlam',          37),
    ('REW', 'Rewa',            38),
    ('SAG', 'Sagar',           39),
    ('SAT', 'Satna',           40),
    ('SEH', 'Sehore',          41),
    ('SEO', 'Seoni',           42),
    ('SHA', 'Shahdol',         43),
    ('SHJ', 'Shajapur',        44),
    ('SHP', 'Sheopur',         45),
    ('SHV', 'Shivpuri',        46),
    ('SID', 'Sidhi',           47),
    ('SIN', 'Singrauli',       48),
    ('TIK', 'Tikamgarh',       49),
    ('UJJ', 'Ujjain',          50),
    ('UMA', 'Umaria',          51),
    ('VID', 'Vidisha',         52),
    ('MKR', 'Maihar',          53),
    ('NAG', 'Nagda',           54),
    ('PNH', 'Pandhurna',       55)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'MP';

-- =========================================================
-- INDIA — MAHARASHTRA (36 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('AHN', 'Ahmednagar',       1),
    ('AKO', 'Akola',            2),
    ('AMR', 'Amravati',         3),
    ('AUR', 'Aurangabad',       4),
    ('BEE', 'Beed',             5),
    ('BHN', 'Bhandara',         6),
    ('BUL', 'Buldhana',         7),
    ('CHN', 'Chandrapur',       8),
    ('DHU', 'Dhule',            9),
    ('GAD', 'Gadchiroli',      10),
    ('GON', 'Gondia',          11),
    ('HIN', 'Hingoli',         12),
    ('JAL', 'Jalgaon',         13),
    ('JLN', 'Jalna',           14),
    ('KOL', 'Kolhapur',        15),
    ('LAT', 'Latur',           16),
    ('MUM', 'Mumbai City',     17),
    ('MBS', 'Mumbai Suburban',  18),
    ('NGP', 'Nagpur',          19),
    ('NAN', 'Nanded',          20),
    ('NDB', 'Nandurbar',       21),
    ('NSK', 'Nashik',          22),
    ('OSM', 'Osmanabad',       23),
    ('PAL', 'Palghar',         24),
    ('PRB', 'Parbhani',        25),
    ('PUN', 'Pune',            26),
    ('RAI', 'Raigad',          27),
    ('RTN', 'Ratnagiri',       28),
    ('SNG', 'Sangli',          29),
    ('SAT', 'Satara',          30),
    ('SIN', 'Sindhudurg',      31),
    ('SOL', 'Solapur',         32),
    ('THN', 'Thane',           33),
    ('WAR', 'Wardha',          34),
    ('WAS', 'Washim',          35),
    ('YAV', 'Yavatmal',        36)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'MH';

-- =========================================================
-- INDIA — MANIPUR (16 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('BIS', 'Bishnupur',        1),
    ('CHA', 'Chandel',          2),
    ('CHU', 'Churachandpur',    3),
    ('IMP', 'Imphal East',      4),
    ('IMW', 'Imphal West',      5),
    ('JIR', 'Jiribam',          6),
    ('KAK', 'Kakching',         7),
    ('KAM', 'Kamjong',          8),
    ('KAN', 'Kangpokpi',        9),
    ('NNY', 'Noney',           10),
    ('PHE', 'Pherzawl',        11),
    ('SEK', 'Senapati',        12),
    ('TAM', 'Tamenglong',      13),
    ('TEN', 'Tengnoupal',      14),
    ('THO', 'Thoubal',         15),
    ('UKH', 'Ukhrul',          16)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'MN';

-- =========================================================
-- INDIA — MEGHALAYA (12 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('EGH', 'East Garo Hills',         1),
    ('EJH', 'East Jaintia Hills',       2),
    ('EKH', 'East Khasi Hills',         3),
    ('NGA', 'North Garo Hills',         4),
    ('RIB', 'Ri Bhoi',                  5),
    ('SGA', 'South Garo Hills',         6),
    ('SWG', 'South West Garo Hills',    7),
    ('SWK', 'South West Khasi Hills',   8),
    ('WGA', 'West Garo Hills',          9),
    ('WJH', 'West Jaintia Hills',      10),
    ('WKH', 'West Khasi Hills',        11),
    ('EKJ', 'Eastern West Khasi Hills',12)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'ML';

-- =========================================================
-- INDIA — MIZORAM (11 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('AIZ', 'Aizawl',          1),
    ('CHA', 'Champhai',        2),
    ('HNA', 'Hnahthial',       3),
    ('KHW', 'Khawzawl',        4),
    ('KOL', 'Kolasib',         5),
    ('LAW', 'Lawngtlai',       6),
    ('LUN', 'Lunglei',         7),
    ('MAM', 'Mamit',           8),
    ('SAI', 'Saitual',         9),
    ('SER', 'Serchhip',       10),
    ('SIH', 'Siaha',          11)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'MZ';

-- =========================================================
-- INDIA — NAGALAND (16 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('CHU', 'Chumoukedima',     1),
    ('DIM', 'Dimapur',          2),
    ('KIP', 'Kiphire',          3),
    ('KOH', 'Kohima',           4),
    ('LON', 'Longleng',         5),
    ('MOK', 'Mokokchung',       6),
    ('MON', 'Mon',              7),
    ('NOR', 'Noklak',           8),
    ('PER', 'Peren',            9),
    ('PHE', 'Phek',            10),
    ('SHA', 'Shamator',        11),
    ('TUE', 'Tuensang',        12),
    ('TSM', 'Tseminyu',        13),
    ('WOK', 'Wokha',           14),
    ('ZUN', 'Zunheboto',       15),
    ('NIU', 'Niuland',         16)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'NL';

-- =========================================================
-- INDIA — PUNJAB (23 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('AMR', 'Amritsar',         1),
    ('BAR', 'Barnala',          2),
    ('BAT', 'Bathinda',         3),
    ('FAR', 'Faridkot',        4),
    ('FAZ', 'Fazilka',          5),
    ('FER', 'Ferozepur',        6),
    ('GUR', 'Gurdaspur',        7),
    ('HOS', 'Hoshiarpur',       8),
    ('JAL', 'Jalandhar',        9),
    ('KAP', 'Kapurthala',      10),
    ('LUD', 'Ludhiana',        11),
    ('MAL', 'Malerkotla',      12),
    ('MAN', 'Mansa',           13),
    ('MOG', 'Moga',            14),
    ('MUK', 'Muktsar',         15),
    ('NAW', 'Nawanshahr',      16),
    ('PAT', 'Pathankot',       17),
    ('PAL', 'Patiala',         18),
    ('RUP', 'Rupnagar',        19),
    ('SAS', 'SAS Nagar',       20),
    ('SAN', 'Sangrur',         21),
    ('TAR', 'Tarn Taran',      22),
    ('SBN', 'Sri Muktsar Sahib', 23)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'PB';

-- =========================================================
-- INDIA — RAJASTHAN (50 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('AJM', 'Ajmer',            1),
    ('ALW', 'Alwar',            2),
    ('ANP', 'Anupgarh',         3),
    ('BAN', 'Banswara',         4),
    ('BAR', 'Baran',            5),
    ('BAM', 'Barmer',           6),
    ('BEA', 'Beawar',           7),
    ('BHA', 'Bharatpur',        8),
    ('BHI', 'Bhilwara',         9),
    ('BIK', 'Bikaner',         10),
    ('BUN', 'Bundi',           11),
    ('CHI', 'Chittorgarh',     12),
    ('CHU', 'Churu',           13),
    ('DAU', 'Dausa',           14),
    ('DEE', 'Deedwana-Kuchaman', 15),
    ('DHO', 'Dholpur',         16),
    ('DUN', 'Dungarpur',       17),
    ('DUS', 'Dudu',            18),
    ('GAN', 'Gangapur City',   19),
    ('HAN', 'Hanumangarh',     20),
    ('JAI', 'Jaipur',          21),
    ('JAR', 'Jaipur Rural',    22),
    ('JAS', 'Jaisalmer',       23),
    ('JAL', 'Jalore',          24),
    ('JHU', 'Jhunjhunu',       25),
    ('JOD', 'Jodhpur',         26),
    ('JDR', 'Jodhpur Rural',   27),
    ('KAR', 'Karauli',         28),
    ('KET', 'Kekri',           29),
    ('KHA', 'Khairthal-Tijara', 30),
    ('KOT', 'Kota',            31),
    ('NAG', 'Nagaur',          32),
    ('NWA', 'Neem Ka Thana',   33),
    ('PAL', 'Pali',            34),
    ('PRA', 'Pratapgarh',      35),
    ('RAJ', 'Rajsamand',       36),
    ('SAL', 'Salumbar',        37),
    ('SAN', 'Sanchore',        38),
    ('SAW', 'Sawai Madhopur',  39),
    ('SHA', 'Shahpura',        40),
    ('SHE', 'Shekhawati',      41),
    ('SIK', 'Sikar',           42),
    ('SIR', 'Sirohi',          43),
    ('SRI', 'Sri Ganganagar',  44),
    ('TON', 'Tonk',            45),
    ('UDA', 'Udaipur',         46),
    ('PHO', 'Phalodi',         47),
    ('SGN', 'Ganganagar',      48),
    ('BAL', 'Balotra',         49),
    ('KPB', 'Kotputli-Behror', 50)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'RJ';

-- =========================================================
-- INDIA — SIKKIM (6 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('EAS', 'East Sikkim',      1),
    ('NOR', 'North Sikkim',     2),
    ('PAK', 'Pakyong',          3),
    ('SOR', 'Soreng',           4),
    ('SOU', 'South Sikkim',     5),
    ('WES', 'West Sikkim',      6)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'SK';

-- =========================================================
-- INDIA — TAMIL NADU (38 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('ARI', 'Ariyalur',             1),
    ('CHG', 'Chengalpattu',         2),
    ('CHE', 'Chennai',              3),
    ('COI', 'Coimbatore',           4),
    ('CUD', 'Cuddalore',            5),
    ('DHR', 'Dharmapuri',            6),
    ('DIN', 'Dindigul',              7),
    ('ERO', 'Erode',                 8),
    ('KAL', 'Kallakurichi',          9),
    ('KAN', 'Kanchipuram',          10),
    ('KAR', 'Karur',                11),
    ('KRI', 'Krishnagiri',          12),
    ('MAD', 'Madurai',              13),
    ('MAY', 'Mayiladuthurai',       14),
    ('NAG', 'Nagapattinam',         15),
    ('KAM', 'Kanyakumari',          16),
    ('NAM', 'Namakkal',             17),
    ('NIL', 'Nilgiris',             18),
    ('PER', 'Perambalur',           19),
    ('PUD', 'Pudukkottai',          20),
    ('RAM', 'Ramanathapuram',       21),
    ('RAN', 'Ranipet',              22),
    ('SAL', 'Salem',                23),
    ('SIV', 'Sivagangai',           24),
    ('TEN', 'Tenkasi',              25),
    ('THA', 'Thanjavur',            26),
    ('THE', 'Theni',                27),
    ('TIR', 'Tiruvallur',           28),
    ('TRP', 'Tirupattur',           29),
    ('TRC', 'Tiruchirappalli',      30),
    ('TRN', 'Tirunelveli',          31),
    ('TVN', 'Tiruvannamalai',       32),
    ('TUT', 'Thoothukudi',          33),
    ('VEL', 'Vellore',              34),
    ('VIL', 'Villupuram',           35),
    ('VIR', 'Virudhunagar',         36),
    ('TRV', 'Tiruvarur',            37),
    ('TNP', 'Tenkasi South',        38)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'TN';

-- =========================================================
-- INDIA — TELANGANA (33 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('ADI', 'Adilabad',              1),
    ('BHD', 'Bhadradri Kothagudem', 2),
    ('HYD', 'Hyderabad',            3),
    ('JAG', 'Jagtial',              4),
    ('JAN', 'Jangaon',              5),
    ('JBC', 'Jayashankar Bhupalpally', 6),
    ('JOG', 'Jogulamba Gadwal',     7),
    ('KAM', 'Kamareddy',            8),
    ('KAR', 'Karimnagar',           9),
    ('KHM', 'Khammam',             10),
    ('KMB', 'Kumuram Bheem Asifabad', 11),
    ('MAH', 'Mahabubabad',         12),
    ('MHN', 'Mahabubnagar',        13),
    ('MAN', 'Mancherial',          14),
    ('MDK', 'Medak',               15),
    ('MCL', 'Medchal-Malkajgiri',  16),
    ('MUL', 'Mulugu',              17),
    ('NAG', 'Nagarkurnool',        18),
    ('NAL', 'Nalgonda',            19),
    ('NAR', 'Narayanpet',          20),
    ('NIR', 'Nirmal',              21),
    ('NIZ', 'Nizamabad',           22),
    ('PED', 'Peddapalli',          23),
    ('RJN', 'Rajanna Sircilla',    24),
    ('RNG', 'Rangareddy',          25),
    ('SAN', 'Sangareddy',          26),
    ('SID', 'Siddipet',            27),
    ('SUR', 'Suryapet',            28),
    ('VIK', 'Vikarabad',           29),
    ('WAN', 'Wanaparthy',          30),
    ('WAR', 'Warangal',            31),
    ('HNK', 'Hanumakonda',         32),
    ('YDB', 'Yadadri Bhuvanagiri', 33)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'TS';

-- =========================================================
-- INDIA — TRIPURA (8 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('DHT', 'Dhalai',           1),
    ('GOM', 'Gomati',           2),
    ('KHW', 'Khowai',           3),
    ('NRT', 'North Tripura',    4),
    ('SEP', 'Sepahijala',       5),
    ('SOT', 'South Tripura',    6),
    ('UNA', 'Unakoti',          7),
    ('WET', 'West Tripura',     8)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'TR';

-- =========================================================
-- INDIA — UTTAR PRADESH (75 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('AGR', 'Agra',              1),
    ('ALG', 'Aligarh',           2),
    ('ALD', 'Prayagraj',         3),
    ('AMB', 'Ambedkar Nagar',    4),
    ('AME', 'Amethi',            5),
    ('AMR', 'Amroha',            6),
    ('AUR', 'Auraiya',           7),
    ('AYO', 'Ayodhya',           8),
    ('AZA', 'Azamgarh',          9),
    ('BAD', 'Badaun',           10),
    ('BAG', 'Baghpat',          11),
    ('BAH', 'Bahraich',         12),
    ('BAL', 'Ballia',           13),
    ('BLR', 'Balrampur',        14),
    ('BAN', 'Banda',            15),
    ('BAR', 'Barabanki',        16),
    ('BRE', 'Bareilly',         17),
    ('BAS', 'Basti',            18),
    ('BIJ', 'Bijnor',           19),
    ('BUD', 'Bulandshahr',      20),
    ('CHA', 'Chandauli',        21),
    ('CHI', 'Chitrakoot',       22),
    ('DEO', 'Deoria',           23),
    ('ETH', 'Etah',             24),
    ('ETA', 'Etawah',           25),
    ('FAR', 'Farrukhabad',      26),
    ('FAT', 'Fatehpur',         27),
    ('FIR', 'Firozabad',        28),
    ('GBN', 'Gautam Buddha Nagar', 29),
    ('GHA', 'Ghaziabad',        30),
    ('GHZ', 'Ghazipur',         31),
    ('GON', 'Gonda',            32),
    ('GOR', 'Gorakhpur',        33),
    ('HAM', 'Hamirpur',         34),
    ('HAP', 'Hapur',            35),
    ('HAR', 'Hardoi',           36),
    ('HAT', 'Hathras',          37),
    ('JAL', 'Jalaun',           38),
    ('JAU', 'Jaunpur',          39),
    ('JHA', 'Jhansi',           40),
    ('KAN', 'Kannauj',          41),
    ('KNP', 'Kanpur Dehat',     42),
    ('KNU', 'Kanpur Nagar',     43),
    ('KAS', 'Kasganj',          44),
    ('KAU', 'Kaushambi',        45),
    ('KUS', 'Kushinagar',       46),
    ('LAK', 'Lakhimpur Kheri',  47),
    ('LAL', 'Lalitpur',         48),
    ('LUC', 'Lucknow',          49),
    ('MAH', 'Maharajganj',      50),
    ('MAI', 'Mainpuri',         51),
    ('MAT', 'Mathura',          52),
    ('MAU', 'Mau',              53),
    ('MER', 'Meerut',           54),
    ('MIR', 'Mirzapur',         55),
    ('MOR', 'Moradabad',        56),
    ('MUZ', 'Muzaffarnagar',    57),
    ('PIL', 'Pilibhit',         58),
    ('PRA', 'Pratapgarh',       59),
    ('RAB', 'Rae Bareli',       60),
    ('RAM', 'Rampur',           61),
    ('SAH', 'Saharanpur',       62),
    ('SAM', 'Sambhal',          63),
    ('SKP', 'Sant Kabir Nagar', 64),
    ('SRN', 'Sant Ravidas Nagar', 65),
    ('SHA', 'Shahjahanpur',     66),
    ('SHR', 'Shamli',           67),
    ('SHW', 'Shravasti',        68),
    ('SDD', 'Siddharthnagar',   69),
    ('SIT', 'Sitapur',          70),
    ('SON', 'Sonbhadra',        71),
    ('SUL', 'Sultanpur',        72),
    ('UNN', 'Unnao',            73),
    ('VAR', 'Varanasi',         74),
    ('MOH', 'Mohamdi',          75)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'UP';

-- =========================================================
-- INDIA — UTTARAKHAND (13 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('ALM', 'Almora',           1),
    ('BAG', 'Bageshwar',        2),
    ('CHA', 'Chamoli',          3),
    ('CHM', 'Champawat',        4),
    ('DEH', 'Dehradun',         5),
    ('HAR', 'Haridwar',         6),
    ('NTL', 'Nainital',         7),
    ('PPG', 'Pauri Garhwal',    8),
    ('PIT', 'Pithoragarh',      9),
    ('RUD', 'Rudraprayag',     10),
    ('TGW', 'Tehri Garhwal',   11),
    ('USK', 'Udham Singh Nagar', 12),
    ('UTK', 'Uttarkashi',      13)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'UK';

-- =========================================================
-- INDIA — WEST BENGAL (23 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('ALI', 'Alipurduar',           1),
    ('BAN', 'Bankura',              2),
    ('BIR', 'Birbhum',              3),
    ('COO', 'Cooch Behar',          4),
    ('DAK', 'Dakshin Dinajpur',     5),
    ('DAR', 'Darjeeling',           6),
    ('HOO', 'Hooghly',              7),
    ('HOW', 'Howrah',               8),
    ('JAL', 'Jalpaiguri',           9),
    ('JHG', 'Jhargram',            10),
    ('KAL', 'Kalimpong',           11),
    ('KOL', 'Kolkata',             12),
    ('MAL', 'Malda',               13),
    ('MUR', 'Murshidabad',         14),
    ('NAD', 'Nadia',               15),
    ('N24', 'North 24 Parganas',   16),
    ('PME', 'Paschim Medinipur',   17),
    ('PBA', 'Paschim Bardhaman',   18),
    ('PUM', 'Purba Medinipur',     19),
    ('PUB', 'Purba Bardhaman',     20),
    ('PUR', 'Purulia',             21),
    ('S24', 'South 24 Parganas',   22),
    ('UTD', 'Uttar Dinajpur',      23)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'WB';

-- =========================================================
-- INDIA — DELHI (11 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('CEN', 'Central Delhi',       1),
    ('EAS', 'East Delhi',          2),
    ('NEW', 'New Delhi',           3),
    ('NOR', 'North Delhi',         4),
    ('NWD', 'North West Delhi',    5),
    ('NED', 'North East Delhi',    6),
    ('SHA', 'Shahdara',            7),
    ('SOU', 'South Delhi',         8),
    ('SED', 'South East Delhi',    9),
    ('SWD', 'South West Delhi',   10),
    ('WES', 'West Delhi',         11)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'DL';

-- =========================================================
-- INDIA — JAMMU AND KASHMIR (20 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('ANA', 'Anantnag',         1),
    ('BAN', 'Bandipora',        2),
    ('BAR', 'Baramulla',        3),
    ('BUD', 'Budgam',           4),
    ('DOD', 'Doda',             5),
    ('GAN', 'Ganderbal',        6),
    ('JAM', 'Jammu',            7),
    ('KAT', 'Kathua',           8),
    ('KIS', 'Kishtwar',         9),
    ('KUL', 'Kulgam',          10),
    ('KUP', 'Kupwara',         11),
    ('PUL', 'Pulwama',         12),
    ('PUN', 'Punch',           13),
    ('RAJ', 'Rajouri',         14),
    ('RAM', 'Ramban',          15),
    ('REA', 'Reasi',           16),
    ('SAM', 'Samba',           17),
    ('SHO', 'Shopian',         18),
    ('SRI', 'Srinagar',        19),
    ('UDH', 'Udhampur',        20)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'JK';

-- =========================================================
-- INDIA — LADAKH (2 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('LEH', 'Leh',     1),
    ('KAR', 'Kargil',  2)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'LA';

-- =========================================================
-- INDIA — CHANDIGARH (1 district)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('CHD', 'Chandigarh', 1)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'CH';

-- =========================================================
-- INDIA — PUDUCHERRY (4 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('PUD', 'Puducherry',   1),
    ('KAR', 'Karaikal',     2),
    ('MAH', 'Mahe',         3),
    ('YAN', 'Yanam',        4)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'PY';

-- =========================================================
-- INDIA — ANDAMAN AND NICOBAR ISLANDS (3 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('NMI', 'Nicobar',              1),
    ('NAN', 'North and Middle Andaman', 2),
    ('SAN', 'South Andaman',        3)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'AN';

-- =========================================================
-- INDIA — DADRA AND NAGAR HAVELI AND DAMAN AND DIU (3 districts)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('DNH', 'Dadra and Nagar Haveli', 1),
    ('DAM', 'Daman',                  2),
    ('DIU', 'Diu',                    3)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'DN';

-- =========================================================
-- INDIA — LAKSHADWEEP (1 district)
-- =========================================================

INSERT INTO district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM state s
CROSS JOIN (VALUES
    ('LKD', 'Lakshadweep', 1)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'LD';

-- =========================================================
-- NON-INDIA COUNTRIES
-- Note: For US, UK, AU, CA the state/province level is
-- already seeded in 05_state.sql. District-level
-- subdivisions for those countries are populated at
-- runtime as needed (too numerous and not operationally
-- required for NSS at seed time).
-- =========================================================
