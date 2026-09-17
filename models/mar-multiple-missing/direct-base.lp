% Query-independent direct BID encoding.
% Each block chooses exactly one alternative with categorical weight p.
person(1,"b","no","untreated").
person(3,"b","yes","treated").
person(8,"a","no","untreated").
person(11,"a","no","untreated").
person(12,"b","yes","untreated").
person(13,"b","no","treated").
person(14,"a","yes","treated").
person(15,"a","no","untreated").
person(18,"a","yes","treated").
1 { chosen(2,1); chosen(2,2) } 1.
person(2,"a","no","treated") :- chosen(2,1).
:~ chosen(2,1). ["-1.2039728043259359"@0,2,1]
person(2,"a","no","untreated") :- chosen(2,2).
:~ chosen(2,2). ["-0.35667494393873228"@0,2,2]
1 { chosen(4,1); chosen(4,2) } 1.
person(4,"a","no","treated") :- chosen(4,1).
:~ chosen(4,1). ["-1.2039728043259359"@0,4,1]
person(4,"a","no","untreated") :- chosen(4,2).
:~ chosen(4,2). ["-0.35667494393873228"@0,4,2]
1 { chosen(5,1); chosen(5,2); chosen(5,3); chosen(5,4) } 1.
person(5,"b","yes","treated") :- chosen(5,1).
:~ chosen(5,1). ["-2.120263536200091"@0,5,1]
person(5,"b","yes","untreated") :- chosen(5,2).
:~ chosen(5,2). ["-2.5257286443082556"@0,5,2]
person(5,"b","no","treated") :- chosen(5,3).
:~ chosen(5,3). ["-2.5257286443082556"@0,5,3]
person(5,"b","no","untreated") :- chosen(5,4).
:~ chosen(5,4). ["-0.3285040669720361"@0,5,4]
1 { chosen(6,1); chosen(6,2); chosen(6,3); chosen(6,4) } 1.
person(6,"b","yes","treated") :- chosen(6,1).
:~ chosen(6,1). ["-2.120263536200091"@0,6,1]
person(6,"b","yes","untreated") :- chosen(6,2).
:~ chosen(6,2). ["-2.5257286443082556"@0,6,2]
person(6,"b","no","treated") :- chosen(6,3).
:~ chosen(6,3). ["-2.5257286443082556"@0,6,3]
person(6,"b","no","untreated") :- chosen(6,4).
:~ chosen(6,4). ["-0.3285040669720361"@0,6,4]
1 { chosen(7,1); chosen(7,2); chosen(7,3); chosen(7,4) } 1.
person(7,"a","yes","treated") :- chosen(7,1).
:~ chosen(7,1). ["-0.57981849525294227"@0,7,1]
person(7,"a","yes","untreated") :- chosen(7,2).
:~ chosen(7,2). ["-1.966112856372833"@0,7,2]
person(7,"a","no","treated") :- chosen(7,3).
:~ chosen(7,3). ["-2.4079456086518722"@0,7,3]
person(7,"a","no","untreated") :- chosen(7,4).
:~ chosen(7,4). ["-1.5606477482646683"@0,7,4]
1 { chosen(9,1); chosen(9,2); chosen(9,3); chosen(9,4) } 1.
person(9,"b","yes","treated") :- chosen(9,1).
:~ chosen(9,1). ["-2.120263536200091"@0,9,1]
person(9,"b","yes","untreated") :- chosen(9,2).
:~ chosen(9,2). ["-2.5257286443082556"@0,9,2]
person(9,"b","no","treated") :- chosen(9,3).
:~ chosen(9,3). ["-2.5257286443082556"@0,9,3]
person(9,"b","no","untreated") :- chosen(9,4).
:~ chosen(9,4). ["-0.3285040669720361"@0,9,4]
1 { chosen(10,1); chosen(10,2); chosen(10,3); chosen(10,4) } 1.
person(10,"b","yes","treated") :- chosen(10,1).
:~ chosen(10,1). ["-2.120263536200091"@0,10,1]
person(10,"b","yes","untreated") :- chosen(10,2).
:~ chosen(10,2). ["-2.5257286443082556"@0,10,2]
person(10,"b","no","treated") :- chosen(10,3).
:~ chosen(10,3). ["-2.5257286443082556"@0,10,3]
person(10,"b","no","untreated") :- chosen(10,4).
:~ chosen(10,4). ["-0.3285040669720361"@0,10,4]
1 { chosen(16,1); chosen(16,2); chosen(16,3); chosen(16,4) } 1.
person(16,"b","yes","treated") :- chosen(16,1).
:~ chosen(16,1). ["-2.120263536200091"@0,16,1]
person(16,"b","yes","untreated") :- chosen(16,2).
:~ chosen(16,2). ["-2.5257286443082556"@0,16,2]
person(16,"b","no","treated") :- chosen(16,3).
:~ chosen(16,3). ["-2.5257286443082556"@0,16,3]
person(16,"b","no","untreated") :- chosen(16,4).
:~ chosen(16,4). ["-0.3285040669720361"@0,16,4]
1 { chosen(17,1); chosen(17,2); chosen(17,3); chosen(17,4) } 1.
person(17,"b","yes","treated") :- chosen(17,1).
:~ chosen(17,1). ["-2.120263536200091"@0,17,1]
person(17,"b","yes","untreated") :- chosen(17,2).
:~ chosen(17,2). ["-2.5257286443082556"@0,17,2]
person(17,"b","no","treated") :- chosen(17,3).
:~ chosen(17,3). ["-2.5257286443082556"@0,17,3]
person(17,"b","no","untreated") :- chosen(17,4).
:~ chosen(17,4). ["-0.3285040669720361"@0,17,4]

#show chosen/2.
