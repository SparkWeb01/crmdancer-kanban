Когда все установите и увидите сайт с формой авторизации, то заведите в базе суперпользователя вот так:

INSERT INTO `crmdb`.`users` (`id`, `login`, `passw`, `exten`, `prefix`, `role`, `ruk_id`, `name`) VALUES (NULL, 'Shef', 'youpassword', NULL, NULL, 'boss', NULL, NULL)

Авторизуйтесь под ним. Создайте сначала руководителя, а потом менеджера. 
Под менеджером можно входить, заводить клиентов и начинать звонить. 

Kanban находится в файле crm_index.html
