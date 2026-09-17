% Query-independent direct BID encoding.
% Each block chooses exactly one alternative with categorical weight p.
person(1,"a","no").
person(3,"a","yes").
person(4,"b","no").
person(6,"a","yes").
1 { chosen(2,1); chosen(2,2) } 1.
person(2,"a","yes") :- chosen(2,1).
:~ chosen(2,1). ["-0.35667494393873245"@0,2,1]
person(2,"a","no") :- chosen(2,2).
:~ chosen(2,2). ["-1.2039728043259361"@0,2,2]
1 { chosen(5,1); chosen(5,2) } 1.
person(5,"b","yes") :- chosen(5,1).
:~ chosen(5,1). ["-1.6094379124341005"@0,5,1]
person(5,"b","no") :- chosen(5,2).
:~ chosen(5,2). ["-0.22314355131420985"@0,5,2]

#show chosen/2.
