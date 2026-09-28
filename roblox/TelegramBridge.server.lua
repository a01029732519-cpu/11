-- ServerScriptService 에 Script 로 넣기
-- 게임 설정 > 보안 > "HTTP 요청 허용" 켜야 함
local HttpService = game:GetService("HttpService")
local Players = game:GetService("Players")

local RELAY_URL = "https://roblox-telegram-relay.<내계정>.workers.dev"
local SECRET = "여기에_SECRET_값" -- 서버 스크립트라 클라이언트에 노출 안 됨
local POLL_SECONDS = 3

local headers = { ["X-Secret"] = SECRET }
local offset = 0

local function request(method, path, body)
	local ok, res = pcall(HttpService.RequestAsync, HttpService, {
		Url = RELAY_URL .. path,
		Method = method,
		Headers = body and { ["X-Secret"] = SECRET, ["Content-Type"] = "application/json" } or headers,
		Body = body and HttpService:JSONEncode(body) or nil,
	})
	if not ok then
		warn("[Telegram] 요청 실패:", res)
		return nil
	end
	if not res.Success then
		warn("[Telegram] HTTP", res.StatusCode, res.Body)
		return nil
	end
	return HttpService:JSONDecode(res.Body)
end

local function send(text)
	task.spawn(request, "POST", "/send", { text = text })
end

-- 텔레그램 명령어 처리
local commands = {}

commands["/players"] = function()
	local names = {}
	for _, p in Players:GetPlayers() do
		table.insert(names, p.Name)
	end
	send(("접속자 %d명: %s"):format(#names, #names > 0 and table.concat(names, ", ") or "없음"))
end

commands["/say"] = function(arg)
	-- 게임 안에 공지 띄우기 (간단히 모든 플레이어 화면에 힌트로 표시)
	for _, p in Players:GetPlayers() do
		local gui = Instance.new("Hint")
		gui.Text = "[공지] " .. arg
		gui.Parent = p:FindFirstChildOfClass("PlayerGui")
		game:GetService("Debris"):AddItem(gui, 5)
	end
	send("공지 보냄: " .. arg)
end

commands["/kick"] = function(arg)
	local target = Players:FindFirstChild(arg)
	if target then
		target:Kick("관리자에 의해 추방됨")
		send(arg .. " 추방 완료")
	else
		send(arg .. " 없음")
	end
end

commands["/help"] = function()
	send("/players - 접속자 목록\n/say 내용 - 게임 공지\n/kick 이름 - 추방\n/help - 도움말")
end

local function handle(text)
	local cmd, arg = text:match("^(%S+)%s*(.*)$")
	if not cmd then return end
	cmd = cmd:gsub("@.*$", "") -- /players@봇이름 형태 대응
	local fn = commands[cmd]
	if fn then
		fn(arg)
	else
		send("모르는 명령어: " .. cmd .. " (/help)")
	end
end

-- 게임 이벤트 -> 텔레그램
Players.PlayerAdded:Connect(function(p)
	send("➕ " .. p.Name .. " 접속")
end)
Players.PlayerRemoving:Connect(function(p)
	send("➖ " .. p.Name .. " 퇴장")
end)

send("🟢 서버 시작 (" .. (game.JobId ~= "" and game.JobId or "Studio") .. ")")

-- 폴링 루프
while true do
	local data = request("GET", "/poll?offset=" .. offset)
	if data and data.ok then
		offset = data.next_offset
		for _, c in data.commands do
			handle(c.text)
		end
	end
	task.wait(POLL_SECONDS)
end
