% Certain observed rows.
person(1,a,yes).
person(3,a,yes).
person(4,b,no).
person(6,b,no).

% Each incomplete observed row induces one BID block. Exactly one joint row
% completion is selected from each block.
1 { chosen(2,yes); chosen(2,no) } 1.
1 { chosen(5,yes); chosen(5,no) } 1.

person(2,a,Disease) :- chosen(2,Disease).
person(5,b,Disease) :- chosen(5,Disease).

% Level-0 weights are natural logarithms of categorical completion
% probabilities. Plingo exponentiates the accumulated weights, so a possible
% world's weight is the product of its selected completion probabilities.
:~ chosen(2,yes). ["-0.35667494393873245"@0,2,yes]
:~ chosen(2,no).  ["-1.2039728043259361"@0,2,no]
:~ chosen(5,yes). ["-1.6094379124341003"@0,5,yes]
:~ chosen(5,no).  ["-0.2231435513142097"@0,5,no]

answer :- person(2,a,yes), person(5,b,yes).
&query(answer).

#show chosen/2.
#show answer/0.
